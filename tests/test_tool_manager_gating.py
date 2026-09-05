"""测试 ToolManager.get_all 的多模态 / Computer Use 工具门控。

不触发 load_all（不加载真实 native/MCP），仅手工塞入带 name 的 stub 工具，
验证 read_image / analyze_image 的多模态互斥，以及 computer_* 系列
是否仅随 ``computer_use=True``（且模型具备视觉）交付。
"""

from types import SimpleNamespace

from api.tools.manager import ToolManager

# 全部相关工具名（含一个无关普通工具作对照）
_NAMES = [
    "read_image",
    "analyze_image",
    "computer_screenshot",
    "computer_click",
    "computer_virtual_click",
    "computer_type",
    "computer_key",
    "computer_scroll",
    "computer_wait",
    "get_weather",
]
_COMPUTER = {
    "computer_screenshot", "computer_click", "computer_virtual_click",
    "computer_type", "computer_key", "computer_scroll", "computer_wait",
}


def _make_manager() -> ToolManager:
    """构造不含真实工具的 ToolManager，仅验证名称过滤。"""
    manager = ToolManager()
    manager._native_tools = [SimpleNamespace(name=n) for n in _NAMES]
    manager._mcp_tools = []
    return manager


def _names(manager: ToolManager, multimodal: bool, computer_use: bool) -> set[str]:
    return {t.name for t in manager.get_all(multimodal=multimodal, computer_use=computer_use)}


def test_vision_model_without_computer_use_excludes_screen_tools() -> None:
    """多模态模型但未开启 Computer Use：保留 read_image，剔除 computer_*。"""
    names = _names(_make_manager(), multimodal=True, computer_use=False)
    assert "read_image" in names
    assert "analyze_image" not in names
    assert names.isdisjoint(_COMPUTER)
    assert "get_weather" in names


def test_non_vision_model_computer_use_is_defensive_filtered() -> None:
    """非多模态模型即便标记 computer_use=True 也不暴露屏幕工具（无法读取截图）。"""
    names = _names(_make_manager(), multimodal=False, computer_use=True)
    assert "read_image" not in names
    assert "analyze_image" in names
    assert names.isdisjoint(_COMPUTER)


def test_vision_model_with_computer_use_enables_screen_tools() -> None:
    """多模态模型 + Computer Use 开启：computer_* 系列完整交付。"""
    names = _names(_make_manager(), multimodal=True, computer_use=True)
    assert names >= _COMPUTER
    assert "read_image" in names
    assert "analyze_image" not in names


def test_non_vision_model_defaults() -> None:
    """默认（非多模态、未开启 Computer Use）：read_image 与 computer_* 均剔除。"""
    names = _names(_make_manager(), multimodal=False, computer_use=False)
    assert "read_image" not in names
    assert "analyze_image" in names
    assert names.isdisjoint(_COMPUTER)
    assert "get_weather" in names
