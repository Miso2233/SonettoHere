"""Agent 图构建 — 自建 ReAct StateGraph。


图结构：（箭头为固定/条件边）

                                      ┌─→ [tools] → [inject_pending] ─┐
                                      │                               ↓
        START → [retrieve_memory] → [agent] ◄─────────────────────────┘
          ↑                           │
          |                           └─→ [ltm_write] → [check_pending]
          |                                                   │
          └───────────────────  队列非空 → 注入 + 跳回 START  │ 队列为空 → END


`retrieve_memory` 节点在每轮用户输入时，根据最新的 HumanMessage 语义检索长期记忆，
将结果以 HumanMessage（【相关记忆】…）的形式追加到 `messages` 列表中，紧随触发它的
用户消息之后。旧轮次的记忆消息随历史保留，不会主动清除。

`inject_pending` 节点连接 `tools` → `agent`，是**工具间隙注入**的独立实现：
每次工具执行完后，将 Agent 输出期间用户发送的排队消息以 HumanMessage 并入图状态，
使下一次 LLM 思考能看到最新输入。队列为空时为空操作。

`check_pending` 节点连接 `ltm_write` → END，是**轮末查询点**：一轮结束后检查会话
挂起队列，队列非空则将排队消息合并注入并以 ``continue_turn`` 跳回 retrieve_memory
（等价于跳回 START），在**图内**完成下一轮编排；队列为空时走向 END。
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Any, Literal, TypedDict

from api.agent import interaction
from api.memory import LongTermMemory

from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.tools import BaseTool
from langgraph._internal._runnable import RunnableCallable
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode


# 彩蛋：Sonetto 就是这个 CompiledStateGraph ✨
Sonetto = CompiledStateGraph


# ── 图状态 ──────────────────────────────────────────


class AgentState(TypedDict, total=False):
    """图状态：对话消息 + 轮末续跑标记。

    ``continue_turn`` 由轮末查询点（check_pending）写入：为 ``True`` 时
    条件边跳回 retrieve_memory，形成图内多轮循环（内置下一轮编排）。
    """
    messages: Annotated[list[BaseMessage], add_messages]
    continue_turn: bool


# ── 条件路由 ──────────────────────────────────────────


def route_after_agent(state: AgentState) -> Literal["tools", "ltm_write"]:
    """模型节点后的条件边路由器。

    带 tool_calls → tools 节点执行工具；
    无 tool_calls → ltm_write 节点持久化本轮对话至长期记忆后结束。
    """
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "ltm_write"


def route_after_check(state: AgentState) -> str:
    """轮末查询点后的条件边路由器。

    队列仍有待注入消息 → 跳回 retrieve_memory（等价于跳回 START）；
    否则 → END 结束本轮图执行。
    """
    if state.get("continue_turn"):
        return "retrieve_memory"
    return END


# ── 图节点类 ──────────────────────────────────────────


class RetrieveMemoryNode:
    """检索长期记忆，以 HumanMessage 追加到 messages 中。

    按 (session_id, memory_id) 去重——同一会话中已注入过的记忆不再重复注入。

    查询策略：拼接所有真实用户输入（排除内存注入的【相关记忆】消息），
    而非仅取最后一条消息，使语义检索能够感知完整对话上下文。
    """

    # 跨实例去重状态（key=session_id, value=已注入的记忆 ID 集合）
    _seen: dict[str, set[str]] = {}

    def __init__(self, ltm: LongTermMemory | None) -> None:
        self._ltm = ltm

    async def __call__(
        self, state: AgentState, config: RunnableConfig
    ) -> dict[str, list[BaseMessage]]:
        if self._ltm is None:
            return {}

        # 失忆模式：跳过记忆提取
        if config["configurable"].get("skip_recall", False):
            return {}

        # 收集所有真实用户输入：HumanMessage 且不含记忆注入标记
        from api.memory.long_term import MEMORY_INJECTION_MARKER  # noqa: PLC0415

        user_queries: list[str] = []
        for msg in state["messages"]:
            if not isinstance(msg, HumanMessage):
                continue
            content = msg.content
            if isinstance(content, list):
                text_parts = [
                    p.get("text", "")
                    for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                ]
                content = " ".join(text_parts) if text_parts else ""
            if not content:
                continue
            if content.startswith(MEMORY_INJECTION_MARKER):
                continue
            user_queries.append(content)

        if not user_queries:
            return {}

        query = "\n".join(user_queries)

        # 延迟导入避免循环依赖
        from api.events.memory import MemorySender  # noqa: PLC0415
        from api.memory import RetrievalMode  # noqa: PLC0415

        turn_id = config["configurable"].get("turn_id", "")
        session_id = config["configurable"]["thread_id"]

        # ═══ 注册 skip 交互 Future ═══
        interaction_id, skip_future = interaction.register()

        # 通知前端开始搜索（携带 interaction_id 供跳过按钮回传）
        ws_sender = MemorySender.from_context()
        if ws_sender:
            await ws_sender.memory_search_start(
                turn_id=turn_id,
                interaction_id=interaction_id,
            )

        # ═══ 异步检索 vs 跳过信号 竞速 ═══
        retrieval_task = asyncio.create_task(
            self._ltm.get_related_memory_from_async(query, mode=RetrievalMode.LLM)
        )

        done, pending = await asyncio.wait(
            [retrieval_task, skip_future],
            return_when=asyncio.FIRST_COMPLETED,
        )

        if skip_future.done():
            # ← 用户点击了跳过：放弃检索结果，不注入记忆
            retrieval_task.cancel()
            try:
                await retrieval_task
            except asyncio.CancelledError:
                pass
            interaction.cleanup(interaction_id)
            if ws_sender:
                await ws_sender.memory_search_skipped()
            return {}

        # → 检索正常完成
        interaction.cleanup(interaction_id)
        results = retrieval_task.result()

        if not results:
            if ws_sender:
                await ws_sender.memory_search_done(total=0, fresh=0)
            return {}

        # 按会话去重（以记忆 ID 为标识）
        seen_ids = RetrieveMemoryNode._seen.setdefault(session_id, set())
        fresh: list[dict[str, str]] = []
        for r in results:
            mid = r["id"]
            if mid in seen_ids:
                continue
            seen_ids.add(mid)
            fresh.append(r)

        # 通知前端搜索完成（含重复量和净增量）
        if ws_sender:
            await ws_sender.memory_search_done(total=len(results), fresh=len(fresh))

        if not fresh:
            return {}

        return {"messages": [self._build_memory_message(fresh)]}

    @staticmethod
    def _build_memory_message(results: list[dict[str, str]]) -> HumanMessage:
        """将记忆检索结果格式化为一条 HumanMessage。"""
        from api.memory.long_term import MEMORY_INJECTION_MARKER  # noqa: PLC0415

        lines = [MEMORY_INJECTION_MARKER]
        for r in results:
            lines.append(f"- [{r['theme']}] {r['description']}")
        return HumanMessage(content="\n".join(lines))


class CallAgentNode:
    """调用 LLM，返回新的 AIMessage。"""

    def __init__(self, system_message: SystemMessage, model_with_tools: Runnable[LanguageModelInput, AIMessage]) -> None:
        self._system_message = system_message
        self._model_with_tools = model_with_tools

    async def __call__(
        self, state: AgentState, config: RunnableConfig
    ) -> dict[str, Any]:
        messages = [self._system_message] + state["messages"]
        response = await self._model_with_tools.ainvoke(messages, config)
        return {"messages": [response]}


class InjectPendingNode:
    """工具间隙注入节点 — 连接 tools → agent 之间。

    每次工具执行完成后，将 Agent 输出期间用户发送的排队消息以
    HumanMessage 形式并入图状态，使下一次 LLM 思考能看到最新输入。
    通过返回值持久化（LangGraph 的 add_messages 仅持久化节点返回值）。

    文本-only 注入：含图片的排队消息走轮末 new_turn 路径的多模态处理。
    """

    async def __call__(
        self, state: AgentState, config: RunnableConfig
    ) -> dict[str, list[HumanMessage]]:
        # 延迟导入避免循环依赖
        from api.agent.turn import now_timestamp  # noqa: PLC0415
        from api.events import TurnSender  # noqa: PLC0415
        from api.session.manager import session_manager  # noqa: PLC0415

        sid = config["configurable"]["thread_id"]
        session = session_manager.get(sid)
        if session is None or not session.has_pending():
            return {}

        pending = session.drain_pending()
        # 时间戳随注入进入 LLM 上下文；pending_consumed 推送干净文本供前端展示
        injected = [HumanMessage(content=p.text + now_timestamp()) for p in pending]
        sender = TurnSender.from_session(session)
        if sender:
            await sender.pending_consumed(
                [{"pending_id": p.pending_id, "text": p.text} for p in pending],
                mode="mid_turn",
            )
        return {"messages": injected}


class LtmWriteNode:
    """将本轮对话投递到 LTM 后台队列，异步更新 memory.yaml。

    不阻塞——send_history_from_session 仅做 queue.put 后立即返回。
    当 ``ltm is None`` 或 ``private_mode is True`` 时跳过。
    """

    def __init__(self, ltm: LongTermMemory | None) -> None:
        self._ltm = ltm

    async def __call__(
        self, state: AgentState, config: RunnableConfig
    ) -> dict[str, Any]:
        if self._ltm is None:
            return {}

        if config["configurable"]["private_mode"]:
            return {}

        # 延迟导入避免循环依赖
        from api.session.manager import session_manager  # noqa: PLC0415

        sid = config["configurable"]["thread_id"]
        session = session_manager.get(sid)
        if session is None:
            return {}

        turn_id = config["configurable"].get("turn_id", "")
        await self._ltm.send_history_from_session(session, turn_id=turn_id)
        return {}


class CheckPendingNode:
    """轮末查询点 — 连接 ltm_write → END。

    一轮结束后，在**节点内按确定顺序**推送本轮收尾事件，再检查会话挂起队列：
    1. ``answer`` — 本轮最终回答（最后一条 AIMessage 内容）；
    2. ``done``   — 收尾当前轮（含逐轮上下文用量）；
    3. 队列非空 → 合并排队消息注入图状态，发 ``pending_consumed(new_turn)``，
       ``continue_turn`` 置 True 让条件边跳回 retrieve_memory（等价于跳回 START）；
       队列为空 → 走向 END。

    逐轮消息计数（user+assistant 一对）也在此完成，取代外层编排层的计数。
    文本-only 注入：含图片的排队消息暂以文本并入，多模态路径待后续增强。
    """

    async def __call__(
        self, state: AgentState, config: RunnableConfig
    ) -> dict[str, Any]:
        # 延迟导入避免循环依赖（turn.py 顶层导入 build_agent）
        from api.agent.context_usage import estimate_context_usage_from_session  # noqa: PLC0415
        from api.agent.turn import merge_pending_batch, now_timestamp  # noqa: PLC0415
        from api.events import TurnSender  # noqa: PLC0415
        from api.session.manager import session_manager  # noqa: PLC0415

        sid = config["configurable"]["thread_id"]
        session = session_manager.get(sid)
        if session is None:
            return {"continue_turn": False}

        sender = TurnSender.from_session(session)

        # ── 本轮 answer + 消息计数 ──
        last_ai = next(
            (m for m in reversed(state["messages"]) if isinstance(m, AIMessage)),
            None,
        )
        if last_ai is not None:
            if sender:
                await sender.answer(str(last_ai.content))
            if getattr(last_ai, "content", None):
                session.increment_messages()  # user+assistant 一对

        # ── 本轮 done（含上下文用量） ──
        if sender:
            usage = await estimate_context_usage_from_session(
                session,
                config["configurable"].get("system_prompt", ""),
                max_tokens=config["configurable"].get("max_tokens", 256_000),
                model_name=config["configurable"].get("model_name", ""),
            )
            await sender.done(config["configurable"].get("turn_id", ""), usage)

        if not session.has_pending():
            return {"continue_turn": False}

        # ── 队列非空：合并注入 + 跳回 START ──
        pending = session.drain_pending()
        text, _, _ = merge_pending_batch(pending)
        # 时间戳随注入进入 LLM 上下文；pending_consumed 推送干净合并文本供前端展示
        injected = [HumanMessage(content=text + now_timestamp())]

        if sender:
            await sender.pending_consumed(
                [{"pending_id": p.pending_id, "text": p.text} for p in pending],
                mode="new_turn",
                text=text,
            )

        return {"messages": injected, "continue_turn": True}


# ── 图构建 ──────────────────────────────────────────────


def build_agent(
    model: BaseChatModel,
    tools: list[BaseTool],
    system_prompt: str,
    checkpointer: BaseCheckpointSaver,
    ltm: LongTermMemory | None = None,
) -> Sonetto:
    """构建 ReAct Agent 图。

    .. rubric:: 图结构

    ::

                                      ┌─→ [tools] → [inject_pending] ─┐
                                      │                               ↓
        START → [retrieve_memory] → [agent] ◄─────────────────────────┘
          ↑                           │
          |                           └─→ [ltm_write] → [check_pending]
          |                                                   │
          └───────────────────  队列非空 → 注入 + 跳回 START  │ 队列为空 → END



    - **retrieve_memory** — 每轮 HumanMessage 时通过 ``ltm`` 语义检索长期记忆，
      以 HumanMessage 追加到 messages
    - **agent** — 调用 LLM，可绑定工具
    - **tools** — 执行工具调用
    - **inject_pending** — 工具间隙注入：tools 之后将排队消息并入图状态（空操作时为空）
    - **ltm_write** — 将本轮对话投递到 LTM 后台队列以更新 memory.yaml
    - **check_pending** — 轮末查询点：队列非空时合并注入并跳回 retrieve_memory
      （图内完成下一轮编排），为空时走向 END

    .. rubric:: config.configurable 支持的键

    传入 ``astream_events(inputs, config={"configurable": {...}})`` 时：

    ==============  =====  ====================================================
    键              类型    说明
    ==============  =====  ====================================================
    ``thread_id``    str    **必需**。会话 ID，传给 checkpointer 读写状态。
    ``private_mode``  bool   **必需**。为 ``True`` 时跳过 ltm_write 节点。
    ``skip_recall``   bool   **必需**。为 ``True`` 时跳过 retrieve_memory 节点（失忆模式）。
    ==============  =====  ====================================================

    Args:
        model: LangChain 聊天模型实例（如 ChatOpenAI）。
        tools: 工具列表，传给 ToolNode 统一调度。
        system_prompt: 系统提示词，作为 SystemMessage 注入每次模型调用。
        checkpointer: 检查点存储器（必填，由调用方提供）。
        ltm: LongTermMemory 实例。提供时启用 ``retrieve_memory`` 和
            ``ltm_write`` 节点；为 ``None`` 时两节点均为空操作。

    Returns:
        编译后的 ``CompiledStateGraph``（即 ``Sonetto``）。
    """

    # ── 构造节点实例 ─────────────────────────────────
    retrieve_memory_node = RetrieveMemoryNode(ltm)
    agent_node = CallAgentNode(
        SystemMessage(content=system_prompt),
        model.bind_tools(tools),
    )
    inject_pending_node = InjectPendingNode()
    ltm_write_node = LtmWriteNode(ltm)
    check_pending_node = CheckPendingNode()
    tool_node = ToolNode(tools)

    # ── 组装图 ────────────────────────────────────────
    builder = StateGraph(AgentState)

    builder.add_node(
        "retrieve_memory",
        RunnableCallable(None, retrieve_memory_node, name="retrieve_memory", trace=False),
    )
    builder.add_node(
        "agent",
        RunnableCallable(None, agent_node, name="agent", trace=False),
    )
    builder.add_node(
        "inject_pending",
        RunnableCallable(None, inject_pending_node, name="inject_pending", trace=False),
    )
    builder.add_node("tools", tool_node)
    builder.add_node(
        "ltm_write",
        RunnableCallable(None, ltm_write_node, name="ltm_write", trace=False),
    )
    builder.add_node(
        "check_pending",
        RunnableCallable(None, check_pending_node, name="check_pending", trace=False),
    )

    builder.add_edge(START, "retrieve_memory")
    builder.add_edge("retrieve_memory", "agent")
    builder.add_conditional_edges("agent", route_after_agent)
    builder.add_edge("tools", "inject_pending")
    builder.add_edge("inject_pending", "agent")
    builder.add_edge("ltm_write", "check_pending")
    builder.add_conditional_edges("check_pending", route_after_check)

    return builder.compile(checkpointer=checkpointer)
