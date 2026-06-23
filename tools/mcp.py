"""MCP 工具管理器 — 从 YAML 配置加载的通用 MCP 客户端桥接框架。

所有 MCP 工具统一使用前端 ToolCallCard 兜底组件展示，
无需在 registry.ts 中注册专属气泡组件。
"""

from pathlib import Path
from typing import Annotated, Any, Literal, Union

import yaml
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from pydantic import BaseModel, Field

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "mcp_servers.yaml"

_client: MultiServerMCPClient | None = None
_tools: list[BaseTool] | None = None
_config: list["MCPServerConfig"] | None = None
_last_error: str | None = None


# ═══════════════════════════════════════════════════════════════════════
# Pydantic 配置模型
# ═══════════════════════════════════════════════════════════════════════


class _BaseServerMixin(BaseModel):
    """所有 MCP 服务器配置变体共享的字段。"""

    server_id: str
    enabled: bool = True
    description: str = ""


class StdioServerConfig(_BaseServerMixin):
    """stdio 传输 — 本地子进程。"""

    transport: Literal["stdio"] = "stdio"
    command: str
    args: list[str] = []
    env: dict[str, str] | None = None
    cwd: str | None = None

    def to_connection(self) -> dict[str, Any]:
        conn: dict[str, Any] = {
            "transport": "stdio",
            "command": self.command,
            "args": self.args,
        }
        if self.env is not None:
            conn["env"] = self.env
        if self.cwd is not None:
            conn["cwd"] = self.cwd
        return conn


class SSEServerConfig(_BaseServerMixin):
    """SSE 传输 — HTTP 服务器推送事件。"""

    transport: Literal["sse"] = "sse"
    url: str
    headers: dict[str, str] | None = None
    timeout: float | None = None
    sse_read_timeout: float | None = None

    def to_connection(self) -> dict[str, Any]:
        conn: dict[str, Any] = {
            "transport": "sse",
            "url": self.url,
        }
        if self.headers is not None:
            conn["headers"] = self.headers
        if self.timeout is not None:
            conn["timeout"] = self.timeout
        if self.sse_read_timeout is not None:
            conn["sse_read_timeout"] = self.sse_read_timeout
        return conn


class StreamableHttpServerConfig(_BaseServerMixin):
    """Streamable HTTP 传输 — MCP 2025-03-26 规范。"""

    transport: Literal["streamable_http"] = "streamable_http"
    url: str
    headers: dict[str, str] | None = None
    timeout: float | None = None

    def to_connection(self) -> dict[str, Any]:
        conn: dict[str, Any] = {
            "transport": "streamable_http",
            "url": self.url,
        }
        if self.headers is not None:
            conn["headers"] = self.headers
        if self.timeout is not None:
            conn["timeout"] = self.timeout
        return conn


class WebsocketServerConfig(_BaseServerMixin):
    """WebSocket 传输。"""

    transport: Literal["websocket"] = "websocket"
    url: str

    def to_connection(self) -> dict[str, Any]:
        return {"transport": "websocket", "url": self.url}


MCPServerConfig = Annotated[
    Union[
        StdioServerConfig,
        SSEServerConfig,
        StreamableHttpServerConfig,
        WebsocketServerConfig,
    ],
    Field(discriminator="transport"),
]


class MCPServersConfigFile(BaseModel):
    """config/mcp_servers.yaml 的根结构。"""

    mcp_servers: list[MCPServerConfig] = []


# ═══════════════════════════════════════════════════════════════════════
# 配置加载
# ═══════════════════════════════════════════════════════════════════════


def load_mcp_config() -> list[MCPServerConfig]:
    """解析并验证 config/mcp_servers.yaml。"""
    global _last_error, _config

    if _config is not None:
        return _config

    if not _CONFIG_PATH.exists():
        _config = []
        return []

    try:
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        validated = MCPServersConfigFile(**raw)
        _config = validated.mcp_servers
        _last_error = None
        return _config
    except Exception as exc:
        _last_error = f"加载 MCP 配置失败: {exc}"
        print(f"[mcp] {_last_error}")
        _config = []
        return []


# ═══════════════════════════════════════════════════════════════════════
# 生命周期
# ═══════════════════════════════════════════════════════════════════════


async def init_mcp_tools() -> list[BaseTool]:
    """从 YAML 加载配置并初始化 MCP 客户端。

    仅连接 enabled=True 的服务器，工具名自动加 {serverId}_ 前缀。
    """
    global _client, _tools, _last_error

    if _tools is not None:
        return _tools

    configs = load_mcp_config()
    enabled = [c for c in configs if c.enabled]
    if not enabled:
        _tools = []
        return _tools

    connections: dict[str, Any] = {}
    server_errors: list[str] = []

    for cfg in enabled:
        try:
            connections[cfg.server_id] = cfg.to_connection()
        except Exception as exc:
            msg = f"服务器 '{cfg.server_id}' 连接构建失败: {exc}"
            server_errors.append(msg)
            print(f"[mcp] {msg}")

    if not connections:
        _tools = []
        if server_errors:
            _last_error = "; ".join(server_errors)
        return _tools

    try:
        _client = MultiServerMCPClient(
            connections=connections,
            tool_name_prefix=True,
        )
        _tools = await _client.get_tools()
        _last_error = None

        for cfg in enabled:
            prefix = f"{cfg.server_id}_"
            count = sum(1 for t in _tools if t.name.startswith(prefix))
            print(f"[mcp] 服务器 '{cfg.server_id}' 已加载 {count} 个工具")
    except Exception as exc:
        _last_error = f"初始化 MCP 客户端失败: {exc}"
        print(f"[mcp] {_last_error}")
        _tools = []

    return _tools


async def close_mcp():
    """释放 MCP 客户端资源。

    MultiServerMCPClient v0.2.2 没有 close() 方法（会话是短暂的，
    每次工具调用创建/销毁），这里仅重置模块级状态。
    """
    global _client, _tools, _config, _last_error
    _client = None
    _tools = None
    _config = None
    _last_error = None


# ═══════════════════════════════════════════════════════════════════════
# 热加载 & 查询
# ═══════════════════════════════════════════════════════════════════════


async def reload_mcp() -> list[BaseTool]:
    """重新加载 MCP 配置并重建连接。

    失败时保留旧状态不变。
    """
    global _client, _tools, _config, _last_error

    old_client = _client
    old_tools = _tools
    old_config = _config
    old_error = _last_error

    # 清除缓存，强制重新加载
    _client = None
    _tools = None
    _config = None
    _last_error = None

    try:
        result = await init_mcp_tools()
        if _tools is None:
            _tools = []
        return _tools
    except Exception as exc:
        # 恢复旧状态
        _client = old_client
        _tools = old_tools
        _config = old_config
        _last_error = old_error
        raise


def get_mcp_servers_info() -> list[dict[str, Any]]:
    """返回序列化的服务器配置（供 API 使用）。"""
    global _config
    if _config is None:
        load_mcp_config()

    if not _config:
        return []

    result = []
    for c in _config:
        info: dict[str, Any] = {
            "server_id": c.server_id,
            "transport": c.transport,
            "enabled": c.enabled,
            "description": c.description,
        }
        if _tools:
            prefix = f"{c.server_id}_"
            info["tool_count"] = sum(1 for t in _tools if t.name.startswith(prefix))
        else:
            info["tool_count"] = 0
        result.append(info)
    return result


def get_mcp_error() -> str | None:
    """返回最近一次的错误信息（无错误则返回 None）。"""
    return _last_error
