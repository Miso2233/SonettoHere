"""REST API — MCP 服务器配置查看与热加载。"""

from fastapi import APIRouter, HTTPException, Request

from tools.mcp import get_mcp_servers_info
from api.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/mcp/servers")
async def list_mcp_servers(request: Request) -> dict:
    """返回所有已配置的 MCP 服务器（含 disabled）。"""
    servers = get_mcp_servers_info()
    mcp_tools = request.app.state.tool_manager.mcp_tools
    return {
        "servers": servers,
        "tool_count": len(mcp_tools),
    }


@router.post("/mcp/reload")
async def reload_mcp_servers(request: Request) -> dict:
    """热加载：重新解析 YAML → 重建连接 → 替换 app.state。

    失败时保留旧工具列表不变。
    """
    try:
        new_tools = await request.app.state.tool_manager.reload_mcp()
        server_info = get_mcp_servers_info()
        return {
            "status": "ok",
            "servers": server_info,
            "tool_count": len(new_tools),
        }
    except Exception as exc:
        logger.exception("MCP 重载失败")
        raise HTTPException(
            status_code=500,
            detail="MCP 重载失败",
        )
