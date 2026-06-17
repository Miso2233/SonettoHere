"""MCP 工具管理器 — 通用 MCP 客户端桥接框架。

保留此模块作为 MCP 基础设施，支持通过 init_mcp_tools() 动态配置各
类 MCP 服务器（如 Word、数据库等）。当前无活跃配置，返回空列表。

如需接入新的 MCP 服务器，在此文件中添加对应的 MultiServerMCPClient
配置即可，前端通过 word_ 前缀规则路由（见 registry.ts）。
"""

from langchain_core.tools import BaseTool

_client = None
_tools: list[BaseTool] | None = None


async def init_mcp_tools() -> list[BaseTool]:
    """初始化 MCP 客户端并返回所有 MCP 工具列表。

    当前无已注册的 MCP 服务器，返回空列表。
    子类可继承或在外部重写此模块的 _client / _tools 全局变量来接入自定义 MCP。
    """
    global _client, _tools
    if _tools is not None:
        return _tools
    _tools = []
    return _tools


async def close_mcp():
    """释放 MCP 客户端资源。"""
    global _client, _tools
    _client = None
    _tools = None
