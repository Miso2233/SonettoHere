"""Provider 管理器 — 按 id 索引。"""

from collections.abc import Iterator
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from api.providers import FALLBACK_CTX, Provider, ProviderConfig
from api.providers.store import ProviderConfigStore


class ProviderManager:
    """管理所有已注册的 Provider，支持按 id 查找和批量遍历。"""

    def __init__(self, store: ProviderConfigStore):
        self._store = store
        self._providers: dict[str, Provider] = {}

    # ── 生命周期 ────────────────────────────────────────

    def load_all(self) -> None:
        """从 store 加载所有 enabled provider 并创建实例。"""
        self._providers.clear()
        for config in self._store.load_all():
            if config.enabled:
                provider = self._build_provider(config)
                self._providers[config.id] = provider

    def reload(self) -> None:
        """重新加载 YAML 配置。"""
        self.load_all()

    # ── 查询 ────────────────────────────────────────────

    def get(self, provider_id: str) -> Provider:
        """按 id 获取 provider，不存在则抛 KeyError。"""
        provider = self._providers.get(provider_id)
        if provider is None:
            msg = f"Provider '{provider_id}' not found or not enabled"
            raise KeyError(msg)
        return provider

    def iter_enabled(self) -> Iterator[Provider]:
        return iter(self._providers.values())

    def has(self, provider_id: str) -> bool:
        return provider_id in self._providers

    @property
    def count(self) -> int:
        return len(self._providers)

    def get_default_provider(self) -> Provider | None:
        """优先返回 is_default_provider=True 的 provider，否则返回第一个 enabled provider。"""
        for provider in self.iter_enabled():
            if provider.config.is_default_provider:
                return provider
        for provider in self.iter_enabled():
            return provider
        return None

    def get_default_context(self) -> tuple[int, str]:
        """返回默认供应商的上下文窗口大小和模型名。"""
        provider = self.get_default_provider()
        if provider is None:
            return FALLBACK_CTX, ""
        model = provider.default_model
        ctx = provider.config.model_context_windows.get(model, FALLBACK_CTX)
        return ctx, model

    def create_llm(
        self, provider_id: str, model_name: str, **kwargs: Any
    ) -> tuple[BaseChatModel, str, int] | None:
        """按指定 provider + model 创建 LLM，返回 (llm, model_name, max_tokens)。
        provider 不存在时返回 None。"""
        try:
            provider = self.get(provider_id)
        except KeyError:
            return None
        llm = provider.create_llm(model_name, **kwargs)
        max_tokens = provider.config.model_context_windows.get(model_name, FALLBACK_CTX)
        return llm, model_name, max_tokens

    def get_default_llm(self, **kwargs: Any) -> BaseChatModel | None:
        """获取默认 provider 的 LLM。无可用 provider 时返回 None。"""
        provider = self.get_default_provider()
        if provider is None:
            return None
        return provider.create_llm(provider.default_model, **kwargs)

    # ── 配置 CRUD（委托 store 并同步缓存）────────────────

    def list_configs(self) -> list[ProviderConfig]:
        """返回所有配置（不论 enabled 与否）。"""
        return self._store.load_all()

    def get_config(self, provider_id: str) -> ProviderConfig | None:
        """按 id 查找配置。"""
        return self._store.get(provider_id)

    def save_config(self, config: ProviderConfig) -> None:
        """保存配置并在加载缓冲。"""
        self._store.save(config)
        self.load_all()

    def delete_config(self, provider_id: str) -> bool:
        """删除配置并在加载缓冲。"""
        result = self._store.delete(provider_id)
        if result:
            self.load_all()
        return result

    # ── Provider 工厂 ──────────────────────────────────

    @staticmethod
    def _build_provider(config: ProviderConfig) -> Provider:
        if config.provider_type == "openai":
            from api.providers.openai_provider import OpenAIProvider

            return OpenAIProvider(config)
        msg = f"Unknown provider type: {config.provider_type}"
        raise ValueError(msg)


# ── 模块级单例 ──────────────────────────────────────────────

_manager: ProviderManager | None = None


def init_manager(store: ProviderConfigStore) -> ProviderManager:
    """初始化模块级 ProviderManager 实例（lifespan 中调用）。"""
    global _manager
    _manager = ProviderManager(store)
    return _manager


def get_manager() -> ProviderManager | None:
    """获取模块级 ProviderManager 实例。"""
    return _manager