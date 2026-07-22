"""Agent 包 — 图构建、系统提示词组装。

外部应优先通过 ``from agent import ...`` 导入，而非直接引用子模块。
"""

from agent.graph import Sonetto, build_agent
from agent.prompts import build_system_prompt, get_system_prompt_parts

__all__ = [
    "build_agent",
    "Sonetto",
    "build_system_prompt",
    "get_system_prompt_parts",
]
