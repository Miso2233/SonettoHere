"""Provider 层单元测试 — build_provider 分发、thinking 能力、模型发现、AnthropicProvider 构造。

均为无网络测试：构造 Provider/LLM 不发起请求，SDK 客户端用 monkeypatch 模拟。
"""

import asyncio
from pathlib import Path

import pytest

from api.providers import ProviderConfig, build_provider
from api.providers.anthropic_provider import DEFAULT_BASE_URL, AnthropicProvider
from api.providers.manager import ProviderManager
from api.providers.openai_provider import OpenAIProvider
from api.providers.opencode_headers import is_opencode_gateway, opencode_session_headers
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


class TestApplyThinking:
    """apply_thinking 能力方法：OpenAI 注入 extra_body，Anthropic 无操作。"""

    def test_openai_enabled_injects_extra_body(self) -> None:
        provider = OpenAIProvider(_config())
        assert provider.apply_thinking({}, True) == {
            "extra_body": {"thinking": {"type": "enabled"}}
        }

    def test_openai_disabled_injects_disabled(self) -> None:
        provider = OpenAIProvider(_config())
        assert provider.apply_thinking({}, False) == {
            "extra_body": {"thinking": {"type": "disabled"}}
        }

    def test_openai_preserves_existing_extra_body(self) -> None:
        provider = OpenAIProvider(_config())
        out = provider.apply_thinking({"extra_body": {"other": 1}}, True)
        assert out == {"extra_body": {"other": 1, "thinking": {"type": "enabled"}}}

    def test_anthropic_is_noop(self) -> None:
        provider = AnthropicProvider(_config(provider_type="anthropic"))
        kwargs = {"extra_body": {"thinking": {"type": "enabled"}}, "temperature": 0.7}
        # 原对象原样返回，不注入也不修改
        assert provider.apply_thinking(kwargs, True) is kwargs


class _FakeModel:
    def __init__(self, model_id: str) -> None:
        self.id = model_id


class _FakeModelsList:
    def __init__(self, ids: list[str]) -> None:
        self.data = [_FakeModel(i) for i in ids]

    async def list(self) -> "_FakeModelsList":
        return self


class _FakeModelsClient:
    """模拟 openai/anthropic SDK 异步客户端（仅需 models.list()）。"""

    def __init__(self, **kwargs: object) -> None:
        self.models = _FakeModelsList(["b-model", "a-model"])


class TestListModels:
    """list_models：返回排序后的模型 ID，SDK 客户端按厂商类型构建。"""

    def test_openai_returns_sorted_ids(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        def fake_client(**kwargs: object) -> _FakeModelsClient:
            captured.update(kwargs)
            return _FakeModelsClient()

        monkeypatch.setattr("openai.AsyncOpenAI", fake_client)
        provider = OpenAIProvider(_config())
        assert asyncio.run(provider.list_models()) == ["a-model", "b-model"]
        assert captured == {
            "api_key": "sk-test",
            "base_url": "https://api.example.com/v1",
            "timeout": 10,
        }

    def test_anthropic_defaults_to_official_base_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        def fake_client(**kwargs: object) -> _FakeModelsClient:
            captured.update(kwargs)
            return _FakeModelsClient()

        monkeypatch.setattr("anthropic.AsyncAnthropic", fake_client)
        provider = AnthropicProvider(_config(provider_type="anthropic", base_url=""))
        assert asyncio.run(provider.list_models()) == ["a-model", "b-model"]
        assert captured["base_url"] == DEFAULT_BASE_URL

    def test_anthropic_passes_custom_base_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        def fake_client(**kwargs: object) -> _FakeModelsClient:
            captured.update(kwargs)
            return _FakeModelsClient()

        monkeypatch.setattr("anthropic.AsyncAnthropic", fake_client)
        provider = AnthropicProvider(
            _config(provider_type="anthropic", base_url="https://proxy.example.com")
        )
        assert asyncio.run(provider.list_models()) == ["a-model", "b-model"]
        assert captured["base_url"] == "https://proxy.example.com"


# ── OpenCode 网关 x-opencode-session 请求头 ───────────────────────────────


class TestOpenCodeGatewayDetection:
    """is_opencode_gateway 对 opencode.ai 及其子域返回 True，其余为 False。"""

    def test_opencode_go_and_zen_urls_are_gateway(self) -> None:
        assert is_opencode_gateway("https://opencode.ai/zen/go/v1")
        assert is_opencode_gateway("https://opencode.ai/zen/v1")

    def test_opencode_subdomain_is_gateway(self) -> None:
        assert is_opencode_gateway("https://go.opencode.ai/zen/go/v1")

    def test_other_hosts_are_not_gateway(self) -> None:
        assert not is_opencode_gateway("https://api.deepseek.com/v1")
        assert not is_opencode_gateway("https://notopencode.ai/v1")
        assert not is_opencode_gateway("")
        assert not is_opencode_gateway("https://opencode.ai.evil.com/v1")


class TestOpenCodeSessionHeaders:
    """opencode_session_headers：网关返回稳定会话头，非网关返回空。"""

    def test_gateway_returns_session_header(self) -> None:
        headers = opencode_session_headers("https://opencode.ai/zen/go/v1", "sk-a")
        assert set(headers) == {"x-opencode-session"}
        assert len(headers["x-opencode-session"]) == 32

    def test_session_id_is_stable_for_same_endpoint(self) -> None:
        first = opencode_session_headers("https://opencode.ai/zen/go/v1", "sk-a")
        second = opencode_session_headers("https://opencode.ai/zen/go/v1", "sk-a")
        assert first == second

    def test_session_id_differs_across_endpoint_or_key(self) -> None:
        a = opencode_session_headers("https://opencode.ai/zen/go/v1", "sk-a")
        b = opencode_session_headers("https://opencode.ai/zen/v1", "sk-a")
        c = opencode_session_headers("https://opencode.ai/zen/go/v1", "sk-b")
        assert a != b
        assert a != c

    def test_non_gateway_returns_empty(self) -> None:
        assert opencode_session_headers("https://api.deepseek.com/v1", "sk-a") == {}


class TestOpenCodeHeaderInjection:
    """create_llm/_async_client 对 OpenCode 网关注入 x-opencode-session。"""

    OPENCODE_URL = "https://opencode.ai/zen/go/v1"

    def test_openai_create_llm_injects_stable_session(self) -> None:
        provider = OpenAIProvider(_config(base_url=self.OPENCODE_URL))
        llm1 = provider.create_llm("test-model")
        llm2 = provider.create_llm("test-model")
        h1 = llm1.default_headers or {}
        h2 = llm2.default_headers or {}
        assert "x-opencode-session" in h1
        assert h1 == h2

    def test_anthropic_create_llm_injects_session(self) -> None:
        provider = AnthropicProvider(
            _config(provider_type="anthropic", base_url=self.OPENCODE_URL)
        )
        llm = provider.create_llm("claude-sonnet-5")
        assert "x-opencode-session" in (llm.default_headers or {})

    def test_non_opencode_create_llm_injects_nothing(self) -> None:
        provider = OpenAIProvider(_config(base_url="https://api.deepseek.com/v1"))
        llm = provider.create_llm("test-model")
        assert llm.default_headers in (None, {})

    def test_callers_default_headers_are_preserved(self) -> None:
        provider = OpenAIProvider(_config(base_url=self.OPENCODE_URL))
        llm = provider.create_llm(
            "test-model", default_headers={"x-custom": "keep-me"}
        )
        headers = llm.default_headers or {}
        assert headers["x-custom"] == "keep-me"
        assert "x-opencode-session" in headers

    def test_openai_async_client_injects_session_for_gateway(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        def fake_client(**kwargs: object) -> _FakeModelsClient:
            captured.update(kwargs)
            return _FakeModelsClient()

        monkeypatch.setattr("openai.AsyncOpenAI", fake_client)
        provider = OpenAIProvider(_config(base_url=self.OPENCODE_URL))
        provider._async_client()
        headers = captured.get("default_headers", {})
        assert isinstance(headers, dict)
        assert "x-opencode-session" in headers
