"""api/dependencies.py 测试 — LLM、系统提示、工具集的惰性单例。"""

from unittest.mock import MagicMock

import api.dependencies as deps


class TestGetLlm:
    """get_llm 测试。"""

    def test_get_llm_no_provider_raises(self):
        """provider_manager 为 None → RuntimeError。"""
        import pytest
        with pytest.raises(RuntimeError, match="No enabled LLM provider"):
            deps.get_llm(provider_manager=None)

    def test_get_llm_empty_provider_raises(self):
        """provider_manager.count == 0 → RuntimeError。"""
        import pytest
        pm = MagicMock()
        pm.count = 0
        with pytest.raises(RuntimeError, match="No enabled LLM provider"):
            deps.get_llm(provider_manager=pm)

    def test_get_llm_with_enabled_provider(self):
        """有 enabled provider → 返回 LLM。"""
        fake_llm = MagicMock()
        fake_provider = MagicMock()
        fake_provider.default_model = "gpt-4"
        fake_provider.create_llm.return_value = fake_llm

        pm = MagicMock()
        pm.count = 1
        pm.iter_enabled.return_value = [fake_provider]

        result = deps.get_llm(provider_manager=pm)

        assert result is fake_llm
        fake_provider.create_llm.assert_called_once_with(
            "gpt-4", temperature=0.7, streaming=True,
        )


class TestGetSystemPrompt:
    """get_system_prompt 测试。"""

    def setup_method(self):
        """每个测试前重置全局缓存。"""
        deps._system_prompt = None

    def test_first_call_calls_build(self, monkeypatch):
        """首次调用调用 build_system_prompt。"""
        monkeypatch.setattr(deps, "build_system_prompt", lambda: "测试提示")
        result = deps.get_system_prompt()
        assert result == "测试提示"

    def test_second_call_returns_cached(self, monkeypatch):
        """第二次调用返回缓存，不重复调用 build_system_prompt。"""
        call_count = [0]

        def fake_build():
            call_count[0] += 1
            return f"prompt-{call_count[0]}"

        monkeypatch.setattr(deps, "build_system_prompt", fake_build)

        first = deps.get_system_prompt()
        second = deps.get_system_prompt()

        assert first == "prompt-1"
        assert second == "prompt-1"  # 缓存，不重新调用
        assert call_count[0] == 1


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
        deps._system_prompt = None
        deps._tools = None

    def teardown_method(self):
        deps._system_prompt = None
        deps._tools = None

    def test_system_prompt_starts_none(self):
        assert deps._system_prompt is None

    def test_tools_starts_none(self):
        assert deps._tools is None
