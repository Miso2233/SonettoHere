"""Agent 图构建 — langchain.agents.create_agent。"""

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver

# 彩蛋：Sonetto 就是这个 CompiledStateGraph ✨
Sonetto = CompiledStateGraph


def build_agent(
    model: BaseChatModel,
    tools: list[BaseTool],
    system_prompt: str,
    checkpointer: BaseCheckpointSaver | None = None,
) -> Sonetto:
    """构建 ReAct Agent 图。

    若提供 checkpointer 则复用（跨轮次持久化状态），
    否则新建 MemorySaver（回退行为）。
    """
    if checkpointer is None:
        checkpointer = MemorySaver()

    return create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=checkpointer,
    )
