"""MCP 工具管理器 — 连接 Office-Word-MCP-Server 并返回 LangChain BaseTool。"""

import sys
from pathlib import Path

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

_client: MultiServerMCPClient | None = None
_tools: list[BaseTool] | None = None

# 包裝腳本路徑（解決服務器 stdout 污染問題）
_WRAPPER_PATH = str(Path(__file__).resolve().parent.parent / "scripts" / "mcp_word_server.py")


async def init_mcp_tools() -> list[BaseTool]:
    """初始化 MCP 客户端并返回所有 MCP 工具（已自动添加 word_ 前缀）。

    初始化失败时返回空列表而非抛出异常，避免阻断整个应用启动。
    """
    global _client, _tools
    if _tools is not None:
        return _tools

    try:
        _client = MultiServerMCPClient(
            {
                "word": {
                    "command": sys.executable,
                    "args": [_WRAPPER_PATH],
                    "transport": "stdio",
                }
            },
            tool_name_prefix=True,
        )
        _tools = await _client.get_tools()
    except Exception as e:
        print(f"[WARN] MCP 工具初始化失败，将跳过 Word 功能: {e}")
        _tools = []
    return _tools


async def close_mcp():
    """釋放 MCP 客户端资源。"""
    global _client, _tools
    _client = None
    _tools = None
