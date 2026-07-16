"""Web API 共享资源 — 工具集的惰性单例。"""

from tools import get_all_tools

_tools: list | None = None


def get_tools() -> list:
    global _tools
    if _tools is None:
        _tools = get_all_tools()
    return _tools
