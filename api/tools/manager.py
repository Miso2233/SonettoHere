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

    # 主 Agent 不再需要长期记忆管理工具（已由 retrieve_memory / ltm_write
    # 图节点替代），此处从 get_all 排除，但保留工具文件本身及 LTM 后台
    # consumer 中的 @tool CRUD 函数不受影响。
    _MEMORY_TOOL_NAMES = frozenset({
        "list_memories", "read_memories", "create_memory",
        "update_memory", "delete_memory", "merge_memories",
    })

    # 依赖模型视觉能力（识图能力）才交付的工具，随模型多模态能力同步启用/剔除。
    # 模型不具备多模态视觉时一律过滤（改用外部分析工具 analyze_image 兜底）。
    _IMAGE_TOOL_NAMES = frozenset({
        "read_image",
    })

    # 屏幕操作（computer use）系列：不跟随模型视觉能力自动暴露，仅当用户显式开启
    # Computer Use 模式（computer_use=True，且模型具备视觉以读取截图）才交付给 LLM。
    _COMPUTER_TOOL_NAMES = frozenset({
        "computer_screenshot", "computer_click",
        "computer_virtual_click", "computer_type", "computer_key",
        "computer_scroll", "computer_wait",
    })

    def get_all(self, multimodal: bool = False, computer_use: bool = False) -> list[BaseTool]:
        """返回合并后的完整工具列表（消费方主要用这个）。

        Args:
            multimodal:  当前 LLM 是否支持多模态（视觉能力）。
                         True → 保留 read_image，过滤 analyze_image；
                         False → 保留 analyze_image，过滤 read_image。
            computer_use: 当前是否开启 Computer Use 屏幕操作模式。
                         computer_* 系列仅在 (multimodal and computer_use) 时交付，
                         即用户显式开启该模式（且模型能读取截图）才暴露。
        """
        tools = self.native_tools + self.mcp_tools
        if multimodal:
            tools = [t for t in tools if t.name != "analyze_image"]
        else:
            tools = [t for t in tools if t.name not in self._IMAGE_TOOL_NAMES]
        if not (multimodal and computer_use):
            tools = [t for t in tools if t.name not in self._COMPUTER_TOOL_NAMES]
        return [t for t in tools if t.name not in self._MEMORY_TOOL_NAMES]

    async def reload_mcp(self) -> list[BaseTool]:
        """热加载 MCP 工具，返回新的 MCP 工具列表。"""
        self._mcp_tools = await reload_mcp()
        return self._mcp_tools

    async def close(self):
        """关闭时清理 MCP 资源。"""
        await close_mcp()
        self._native_tools = None
        self._mcp_tools = None