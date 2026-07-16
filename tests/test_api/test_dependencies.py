"""api/dependencies.py 测试 — 工具集的惰性单例。"""

from unittest.mock import MagicMock

import api.core.dependencies as deps


class TestGetTools:
    """get_tools 测试。"""

    def setup_method(self):
        """每个测试前重置全局缓存。"""
        deps._tools = None

    def test_first_call_calls_get_all(self, monkeypatch):
        """首次调用调用 get_all_tools。"""
        fake_tools = ["tool1", "tool2"]
        monkeypatch.setattr(deps, "get_all_tools", lambda: fake_tools)
        result = deps.get_tools()
        assert result == fake_tools

    def test_second_call_returns_cached(self, monkeypatch):
        """第二次调用返回缓存列表。"""
        call_count = [0]

        def fake_get_all():
            call_count[0] += 1
            return [f"tool-{call_count[0]}"]

        monkeypatch.setattr(deps, "get_all_tools", fake_get_all)

        first = deps.get_tools()
        second = deps.get_tools()

        assert first == ["tool-1"]
        assert second == ["tool-1"]  # 缓存
        assert call_count[0] == 1


class TestGlobalStateReset:
    """确保全局缓存在测试间正确重置。"""

    def setup_method(self):
        deps._tools = None

    def teardown_method(self):
        deps._tools = None

    def test_tools_starts_none(self):
        assert deps._tools is None
