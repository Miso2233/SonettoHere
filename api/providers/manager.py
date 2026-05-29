"""Provider 管理器 — 按 id 索引。"""

from collections.abc import Iterator

from api.providers import Provider, ProviderConfig
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
