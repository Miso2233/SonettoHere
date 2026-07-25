"""Agent 图构建 — 自建 ReAct StateGraph。


图结构：（箭头为固定/条件边）

    START ──→ [retrieve_memory] ──→ [agent] ──→ [tools] ──→ [agent] ──→ ... ──→ END
                                            │                              ↑
                                            └── 无 tool_calls → END ──────┘

`retrieve_memory` 节点在每轮用户输入时，根据最新的 HumanMessage 语义检索长期记忆，
将结果以 HumanMessage（【相关记忆】…）的形式追加到 `messages` 列表中，紧随触发它的
用户消息之后。旧轮次的记忆消息随历史保留，不会主动清除。
"""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph._internal._runnable import RunnableCallable
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.graph.message import MessagesState
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode


# 彩蛋：Sonetto 就是这个 CompiledStateGraph ✨
Sonetto = CompiledStateGraph

# ── 条件路由 ──────────────────────────────────────────


def _route_after_agent(state: MessagesState) -> Literal["tools", "ltm_write"]:
    """模型节点后的条件边路由器。

    带 tool_calls → tools 节点执行工具；
    无 tool_calls → ltm_write 节点持久化本轮对话至长期记忆后结束。
    """
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "ltm_write"


# ── 图构建 ──────────────────────────────────────────────


def _build_memory_message(results: list[dict[str, str]]) -> HumanMessage:
    """将记忆检索结果格式化为一条 HumanMessage。"""
    lines = ["【相关记忆】"]
    for r in results:
        lines.append(f"- [{r['theme']}] {r['description']}")
    return HumanMessage(content="\n".join(lines))


def build_agent(
    model: BaseChatModel,
    tools: list[BaseTool],
    system_prompt: str,
    checkpointer: BaseCheckpointSaver,
    ltm: Any | None = None,
) -> Sonetto:
    """构建 ReAct Agent 图。

    .. rubric:: 图结构

    ::

                                    ↓←  [tools] ←↑
        START ──→ [retrieve_memory] ──→ [agent] ──→  [ltm_write] ──→ END



    - **retrieve_memory** — 每轮 HumanMessage 时通过 ``ltm`` 语义检索长期记忆，
      以 HumanMessage 追加到 messages
    - **agent** — 调用 LLM，可绑定工具
    - **tools** — 执行工具调用
    - **ltm_write** — 将本轮对话投递到 LTM 后台队列以更新 memory.yaml

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
        ltm: LongTermMemory 实例。提供时启用 ``retrieve_memory`` 和
            ``ltm_write`` 节点；为 ``None`` 时两节点均为空操作。

    Returns:
        编译后的 ``CompiledStateGraph``（即 ``Sonetto``）。
    """

    # ── 将外部依赖转换为图内可运行对象 ────────────────
    system_message = SystemMessage(content=system_prompt)
    model_with_tools = model.bind_tools(tools)
    tool_node = ToolNode(tools)

    # ── 记忆检索节点（retrieve_memory） ──────────────
    async def retrieve_memory(state: MessagesState) -> dict[str, list[BaseMessage]]:
        """检索长期记忆，以 HumanMessage 追加到 messages 中。

        仅当最后一条是 HumanMessage（用户本轮新输入）且 ltm 可用时检索；
        工具回圈（ToolMessage 结尾）时不检索，但此前追加的记忆保留在历史中。
        """
        last = state["messages"][-1] if state["messages"] else None
        if not isinstance(last, HumanMessage) or ltm is None:
            return {}

        query = last.content
        if isinstance(query, list):
            text_parts = [
                p.get("text", "")
                for p in query
                if isinstance(p, dict) and p.get("type") == "text"
            ]
            query = " ".join(text_parts) if text_parts else ""

        if not query:
            return {}

        # 延迟导入避免循环依赖
        from api.events.memory import MemorySender  # noqa: PLC0415
        from api.memory import RetrievalMode  # noqa: PLC0415

        # 通知前端开始搜索
        ws_sender = MemorySender.from_context()
        if ws_sender:
            await ws_sender.memory_search_start()

        # BM25 机械检索（~2ms），直接同步调用
        results = ltm.get_related_memory_from(query, mode=RetrievalMode.MECHANICAL)

        # 通知前端搜索完成
        if ws_sender:
            await ws_sender.memory_search_done(count=len(results))

        if not results:
            return {}

        return {"messages": [_build_memory_message(results)]}

    # ── 模型节点（agent） ─────────────────────────────
    async def call_agent(
        state: MessagesState, config: RunnableConfig
    ) -> dict[str, Any]:
        """调用 LLM，返回新的 AIMessage。"""
        messages = [system_message] + state["messages"]
        response = await model_with_tools.ainvoke(messages, config)
        return {"messages": [response]}

    # ── LTM 写入节点（ltm_write） ─────────────────────
    async def ltm_write(
        state: MessagesState, config: RunnableConfig
    ) -> dict[str, Any]:
        """将本轮对话投递到 LTM 后台队列，异步更新 memory.yaml。

        不阻塞——send_history_from_session 仅做 queue.put 后立即返回。
        当 ``ltm is None`` 或 ``private_mode is True`` 时跳过。
        """
        if ltm is None:
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
        await ltm.send_history_from_session(session, turn_id=turn_id)
        return {}

    # ── 组装图 ────────────────────────────────────────
    builder = StateGraph(MessagesState)

    builder.add_node(
        "retrieve_memory",
        RunnableCallable(None, retrieve_memory, name="retrieve_memory", trace=False),
    )
    builder.add_node(
        "agent", RunnableCallable(None, call_agent, name="agent", trace=False),
    )
    builder.add_node("tools", tool_node)
    builder.add_node(
        "ltm_write", RunnableCallable(None, ltm_write, name="ltm_write", trace=False),
    )

    builder.add_edge(START, "retrieve_memory")
    builder.add_edge("retrieve_memory", "agent")
    builder.add_conditional_edges("agent", _route_after_agent)
    builder.add_edge("tools", "agent")
    builder.add_edge("ltm_write", END)

    return builder.compile(checkpointer=checkpointer)
