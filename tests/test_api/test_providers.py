"""Provider 层单元测试 — build_provider 分发、thinking 门控、AnthropicProvider 构造。

均为无网络测试：构造 Provider/LLM 不发起请求。
"""

from pathlib import Path

import pytest

from api.providers import ProviderConfig, build_provider
from api.providers.anthropic_provider import DEFAULT_BASE_URL, AnthropicProvider
from api.providers.manager import ProviderManager
from api.providers.openai_provider import OpenAIProvider
from api.providers.store import ProviderConfigStore


def _config(**overrides: object) -> ProviderConfig:
    base: dict[str, object] = {
        "id": "test-provider",
        "provider_type": "openai",
        "label": "Test",
        "api_key": "sk-test",
        "base_url": "https://api.example.com/v1",
        "models": ["test-model"],
        "enabled": True,
    }
    base.update(overrides)
    return ProviderConfig(**base)


class TestBuildProvider:
    def test_anthropic_type_returns_anthropic_provider(self) -> None:
        assert isinstance(
            build_provider(_config(provider_type="anthropic")), AnthropicProvider
        )

    def test_openai_type_returns_openai_provider(self) -> None:
        assert isinstance(
            build_provider(_config(provider_type="openai")), OpenAIProvider
        )

    def test_openrouter_type_returns_openai_provider(self) -> None:
        # openrouter 也是 OpenAI 兼容协议，仍走 OpenAIProvider
        assert isinstance(
            build_provider(_config(provider_type="openrouter")), OpenAIProvider
        )


class TestAnthropicProviderCreateLlm:
    def test_base_url_empty_uses_official_default(self) -> None:
        provider = AnthropicProvider(_config(provider_type="anthropic", base_url=""))
        llm = provider.create_llm("claude-sonnet-5")
        assert llm.model == "claude-sonnet-5"
        assert llm.anthropic_api_url == DEFAULT_BASE_URL
        assert llm.anthropic_api_key.get_secret_value() == "sk-test"

    def test_custom_base_url_is_passed_through(self) -> None:
        provider = AnthropicProvider(
            _config(provider_type="anthropic", base_url="https://proxy.example.com")
        )
        llm = provider.create_llm("claude-sonnet-5")
        assert llm.anthropic_api_url == "https://proxy.example.com"


class TestGetDefaultLlmThinkingGate:
    def _make_manager(self, tmp_path: Path, provider_type: str) -> ProviderManager:
        store = ProviderConfigStore(tmp_path / "providers.yaml")
        store.save(
            _config(
                provider_type=provider_type,
                id="p",
                models=["test-model"],
                is_default_provider=True,
                default_model="test-model",
            )
        )
        manager = ProviderManager(store)
        manager.load_all()
        return manager

    def test_anthropic_does_not_get_extra_body(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manager = self._make_manager(tmp_path, "anthropic")
        captured: dict[str, object] = {}

        def fake_create_llm(self: object, model: str, **kwargs: object) -> object:
            captured.update(kwargs)
            return object()

        monkeypatch.setattr(AnthropicProvider, "create_llm", fake_create_llm)
        manager.get_default_llm(thinking_enabled=True)
        assert "extra_body" not in captured

    def test_openai_gets_thinking_extra_body(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manager = self._make_manager(tmp_path, "openai")
        captured: dict[str, object] = {}

        def fake_create_llm(self: object, model: str, **kwargs: object) -> object:
            captured.update(kwargs)
            return object()

        monkeypatch.setattr(OpenAIProvider, "create_llm", fake_create_llm)
        manager.get_default_llm(thinking_enabled=True)
        thinking = captured.get("extra_body", {})
        assert isinstance(thinking, dict)
        assert thinking.get("thinking") == {"type": "enabled"}
