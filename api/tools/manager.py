"""统一工具管理器 — 管理 Native 工具与 MCP 工具的生命周期。"""

from langchain_core.tools import BaseTool

from tools import get_all_tools
from tools.mcp import init_mcp_tools, reload_mcp, close_mcp


class ToolManager:
    """统一工具管理器 — 管理 Native 工具与 MCP 工具的生命周期。

    - native_tools: 硬编码注册的 Python 工具（同步加载）
    - mcp_tools: 从 YAML 配置加载的 MCP 工具（异步加载）
    - get_all(): 返回合并后的完整工具列表（消费方主要用这个）
    """

    def __init__(self):
        self._native_tools: list[BaseTool] | None = None
        self._mcp_tools: list[BaseTool] | None = None

    async def load_all(self):
        """初始化所有工具。native（同步）→ MCP（异步）。"""
        self._native_tools = get_all_tools()
        self._mcp_tools = await init_mcp_tools()

    @property
    def native_tools(self) -> list[BaseTool]:
        """仅 native 工具列表，供健康检查等细分场景使用。"""
        assert self._native_tools is not None, "load_all() 未调用"
        return self._native_tools

    @property
    def mcp_tools(self) -> list[BaseTool]:
        """仅 MCP 工具列表，供健康检查 / MCP 列表页使用。"""
        assert self._mcp_tools is not None, "load_all() 未调用"
        return self._mcp_tools

    def get_all(self, multimodal: bool = False) -> list[BaseTool]:
        """返回合并后的完整工具列表（消费方主要用这个）。

        Args:
            multimodal: 当前 LLM 是否支持多模态。
                        True → 保留 read_image，过滤 analyze_image；
                        False → 保留 analyze_image，过滤 read_image。
        """
        tools = self.native_tools + self.mcp_tools
        if multimodal:
            return [t for t in tools if t.name != "analyze_image"]
        else:
            return [t for t in tools if t.name != "read_image"]

    async def reload_mcp(self) -> list[BaseTool]:
        """热加载 MCP 工具，返回新的 MCP 工具列表。"""
        self._mcp_tools = await reload_mcp()
        return self._mcp_tools

    async def close(self):
        """关闭时清理 MCP 资源。"""
        await close_mcp()
        self._native_tools = None
        self._mcp_tools = None