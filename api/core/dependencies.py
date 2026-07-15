"""Web API 共享资源 — 系统提示词、工具集的惰性单例。"""

from agent.prompts import build_system_prompt
from tools import get_all_tools

_system_prompt: str | None = None
_tools: list | None = None


def get_system_prompt() -> str:
    global _system_prompt
    if _system_prompt is None:
        _system_prompt = build_system_prompt()
    return _system_prompt


def get_tools() -> list:
    global _tools
    if _tools is None:
        _tools = get_all_tools()
    return _tools
