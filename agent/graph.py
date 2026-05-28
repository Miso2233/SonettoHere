"""Agent 图构建 — LangGraph create_react_agent。"""

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from agent.state import AgentState


def build_agent(
    model: BaseChatModel,
    tools: list[BaseTool],
    system_prompt: str,
    recursion_limit: int = 120,
    checkpointer: MemorySaver | None = None,
) -> CompiledStateGraph:
    """构建 ReAct Agent 图。

    若提供 checkpointer 则复用（跨轮次持久化状态），
    否则每次新建 MemorySaver（原有行为）。
    """
    if checkpointer is None:
        checkpointer = MemorySaver()

    return create_react_agent(
        model=model,
        tools=tools,
        state_schema=AgentState,
        prompt=system_prompt,
        checkpointer=checkpointer,
    ).with_config({"recursion_limit": recursion_limit})
