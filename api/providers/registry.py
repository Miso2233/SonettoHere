"""Provider 注册表 — 按 id 索引适配器。"""

from collections.abc import Iterator

from api.providers import ProviderAdapter, ProviderConfig
from api.providers.store import ProviderConfigStore


class ProviderRegistry:
    """管理所有已注册的 ProviderAdapter，支持按 id 查找和批量遍历。"""

    def __init__(self, store: ProviderConfigStore):
        self._store = store
        self._adapters: dict[str, ProviderAdapter] = {}

    # ── 生命周期 ────────────────────────────────────────

    def load_all(self) -> None:
        """从 store 加载所有 enabled provider 并创建对应的 adapter。"""
        self._adapters.clear()
        for config in self._store.load_all():
            if config.enabled:
                adapter = self._build_adapter(config)
                self._adapters[config.id] = adapter

    def reload(self) -> None:
        """重新加载 YAML 配置。"""
        self.load_all()

    # ── 查询 ────────────────────────────────────────────

    def get(self, provider_id: str) -> ProviderAdapter:
        """按 id 获取 adapter，不存在则抛 KeyError。"""
        adapter = self._adapters.get(provider_id)
        if adapter is None:
            msg = f"Provider '{provider_id}' not found or not enabled"
            raise KeyError(msg)
        return adapter

    def iter_enabled(self) -> Iterator[ProviderAdapter]:
        return iter(self._adapters.values())

    def has(self, provider_id: str) -> bool:
        return provider_id in self._adapters

    @property
    def count(self) -> int:
        return len(self._adapters)

    # ── 适配器工厂 ─────────────────────────────────────

    @staticmethod
    def _build_adapter(config: ProviderConfig) -> ProviderAdapter:
        if config.provider_type == "openai":
            from api.providers.openai_adapter import OpenAIAdapter

            return OpenAIAdapter(config)
        msg = f"Unknown provider type: {config.provider_type}"
        raise ValueError(msg)
