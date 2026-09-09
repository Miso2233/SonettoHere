"""Agent 图构建 — 自建 ReAct StateGraph。

长期记忆的读取**不在此图内自动进行**：模型按需主动调用 ``memory_search`` 工具
精确检索（失忆模式即不发放该工具）。记忆写入仍由图内 ``ltm_write`` 节点在每轮
收尾投递到后台队列。

图结构：（箭头为固定/条件边）

                                      ┌─→ [tools] → [inject_pending] ─┐
                                      │                               ↓
              START → [agent] ◄───────────────────────────────────────┘
                ↑       │
                │       └─→ [ltm_write] → [check_pending]
                │                                │
                └────  队列非空 → 注入 + 跳回 agent │ 队列为空 → END


`inject_pending` 节点连接 `tools` → `agent`，是**工具间隙注入**的独立实现：
每次工具执行完后，将 Agent 输出期间用户发送的排队消息以 HumanMessage 并入图状态，
使下一次 LLM 思考能看到最新输入。队列为空时为空操作。

`check_pending` 节点连接 `ltm_write` → END，是**轮末查询点**：一轮结束后检查会话
挂起队列，队列非空则将排队消息合并注入并以 ``continue_turn`` 跳回 ``agent``
（图内循环头，等价于回到 START，但不再做记忆检索），在**图内**完成下一轮编排；
队列为空时走向 END。
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, TypedDict

from api.memory import LongTermMemory
from api.utils.messages import flatten_content

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
    条件边跳回 agent，形成图内多轮循环（内置下一轮编排）。
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

    队列仍有待注入消息 → 跳回 ``agent``（图内循环头，相当于回到 START）；
    否则 → END 结束本轮图执行。
    """
    if state.get("continue_turn"):
        return "agent"
    return END


# ── 图节点类 ──────────────────────────────────────────


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
       ``continue_turn`` 置 True 让条件边跳回 ``agent``（图内循环头，相当于回到 START）；
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
                await sender.answer(flatten_content(last_ai.content))
            if getattr(last_ai, "content", None):
                session.increment_messages()  # user+assistant 一对

        # ── 本轮 done（含上下文用量） ──
        if sender:
            usage = await estimate_context_usage_from_session(
                session,
                config["configurable"].get("system_prompt", ""),
                max_tokens=config["configurable"].get("max_tokens", 256_000),
                model_name=config["configurable"].get("model_name", ""),
                studio_name=config["configurable"].get("studio_name"),
            )
            await sender.done(config["configurable"].get("turn_id", ""), usage)

        if not session.has_pending():
            return {"continue_turn": False}

        # ── 队列非空：合并注入 + 跳回 agent（图内循环头） ──
        pending = session.drain_pending()
        text, _, _, _ = merge_pending_batch(pending)
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
              START → [agent] ◄───────────────────────────────────────┘
                ↑       │
                │       └─→ [ltm_write] → [check_pending]
                │                                │
                └────  队列非空 → 注入 + 跳回 agent │ 队列为空 → END

    - **agent** — 调用 LLM，可绑定工具
    - **tools** — 执行工具调用
    - **inject_pending** — 工具间隙注入：tools 之后将排队消息并入图状态（空操作时为空）
    - **ltm_write** — 将本轮对话投递到 LTM 后台队列以更新 memory.yaml
    - **check_pending** — 轮末查询点：队列非空时合并注入并跳回 agent
      （图内完成下一轮编排），为空时走向 END

    长期记忆的读取**不在图内自动进行**：模型按需主动调用 ``memory_search`` 工具
    精确检索（失忆模式下该工具不会被发放给模型）。记忆写入仍由 ``ltm_write`` 完成。

    .. rubric:: config.configurable 支持的键

    传入 ``astream_events(inputs, config={"configurable": {...}})`` 时：

    ==============  =====  ====================================================
    键              类型    说明
    ==============  =====  ====================================================
    ``thread_id``    str    **必需**。会话 ID，传给 checkpointer 读写状态。
    ``private_mode``  bool   **必需**。为 ``True`` 时跳过 ltm_write 节点。
    ==============  =====  ====================================================

    Args:
        model: LangChain 聊天模型实例（如 ChatOpenAI）。
        tools: 工具列表，传给 ToolNode 统一调度。
        system_prompt: 系统提示词，作为 SystemMessage 注入每次模型调用。
        checkpointer: 检查点存储器（必填，由调用方提供）。
        ltm: LongTermMemory 实例。提供时启用 ``ltm_write`` 节点；
            为 ``None`` 时该节点为空操作。

    Returns:
        编译后的 ``CompiledStateGraph``（即 ``Sonetto``）。
    """

    # ── 构造节点实例 ─────────────────────────────────
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

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", route_after_agent)
    builder.add_edge("tools", "inject_pending")
    builder.add_edge("inject_pending", "agent")
    builder.add_edge("ltm_write", "check_pending")
    builder.add_conditional_edges("check_pending", route_after_check)

    return builder.compile(checkpointer=checkpointer)
