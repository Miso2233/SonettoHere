"""Agent 图构建 — 自建 ReAct StateGraph。

等价于 langchain.agents.create_agent() 在项目当前使用场景（无 middleware /
无 structured output / 无 return_direct）下的行为。移除了未使用的逻辑，
保留了完整的等效语义，并为后续扩展预留了显式插入点。

图结构：（箭头为固定/条件边）

    START ──→ [agent] ──→ [tools] ──→ [agent] ──→ ... ──→ END
                          │                            ↑
                          └── 无 tool_calls → END ──────┘

扩展点（tools → agent）：
    将 builder.add_edge("tools", "agent") 替换为
    builder.add_edge("tools", "compress") 即可在每轮工具执行后
    插入上下文自动压缩节点。
"""

from typing import Any, Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph._internal._runnable import RunnableCallable
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.graph.message import MessagesState
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

# 彩蛋：Sonetto 就是这个 CompiledStateGraph ✨
Sonetto = CompiledStateGraph


# ── 条件路由 ──────────────────────────────────────────


def _route_after_agent(state: MessagesState) -> Literal["tools", "__end__"]:
    """模型节点后的条件边路由器。

    检查最后一条消息是否为带 tool_calls 的 AIMessage：
    - 是 → 路由到 tools 节点执行工具
    - 否 → 结束本轮执行（抵达 END）
    """
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END


# ── 图构建 ──────────────────────────────────────────────


def build_agent(
    model: BaseChatModel,
    tools: list[BaseTool],
    system_prompt: str,
    checkpointer: BaseCheckpointSaver,
) -> Sonetto:
    """构建 ReAct Agent 图。

    等价于 ``langchain.agents.create_agent()`` 在当前项目所有使用场景
    （chat 主回路、const session 重建、sub-agent 后台执行）下的行为。

    Args:
        model: LangChain 聊天模型实例（如 ChatOpenAI）。
        tools: 工具列表，传给 ToolNode 统一调度。
        system_prompt: 系统提示词，作为 SystemMessage 注入每次模型调用。
        checkpointer: 检查点存储器（必填，由调用方提供）。

    Returns:
        编译后的 ``CompiledStateGraph``（即 ``Sonetto``），
        支持 ``astream_events``、``aget_state``、``aupdate_state`` 等
        所有下游依赖的方法。
    """

    # ── 将外部依赖转换为图内可运行对象 ────────────────
    system_message = SystemMessage(content=system_prompt)
    model_with_tools = model.bind_tools(tools)
    tool_node = ToolNode(tools)

    # ── 模型节点（agent） ─────────────────────────────
    async def call_agent(
        state: MessagesState, config: RunnableConfig
    ) -> dict[str, Any]:
        """调用 LLM，返回新的 AIMessage。

        将 system_prompt 前置到消息列表头部，调用绑定了工具的模型，
        返回结果作为 ``messages`` 的增量更新。
        """
        messages = [system_message] + state["messages"]
        response = await model_with_tools.ainvoke(messages, config)
        return {"messages": [response]}

    # ── 组装图 ────────────────────────────────────────
    builder = StateGraph(MessagesState)  # type: ignore[type-arg]

    builder.add_node("agent", RunnableCallable(None, call_agent, name="agent", trace=False))
    builder.add_node("tools", tool_node)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", _route_after_agent)
    builder.add_edge("tools", "agent")

    return builder.compile(checkpointer=checkpointer)
