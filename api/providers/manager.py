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
        # 默认 LLM 实例缓存：key=(thinking_enabled, temperature, streaming)
        self._default_llm_cache: dict[tuple[bool, float, bool], BaseChatModel] = {}

    # ── 生命周期 ────────────────────────────────────────

    def load_all(self) -> None:
        """从 store 加载所有 enabled provider 并创建实例。

        provider 集合变化后默认 LLM 缓存一并清空，下次 get_default_llm 重建。
        """
        self._providers.clear()
        self._default_llm_cache.clear()
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
    ) -> BaseChatModel | None:
        """按指定 provider + model 创建 LLM。
        provider 不存在时返回 None。"""
        try:
            provider = self.get(provider_id)
        except KeyError:
            return None
        return provider.create_llm(model_name, **kwargs)

    def get_model_metadata(
        self, provider_id: str | None, model_name: str
    ) -> dict[str, int | bool]:
        """返回指定模型的元数据 dict。

        dict 包含:
          - max_tokens: 模型上下文窗口大小（int）
          - multimodal: 是否支持多模态（bool）

        当 provider_id 为 None 或不存在时，回退到 default provider 查询。
        """
        max_tokens = FALLBACK_CTX
        multimodal = False

        eff_id = provider_id
        if not eff_id:
            default = self.get_default_provider()
            if default:
                eff_id = default.config.id

        if eff_id:
            cfg = self.get_config(eff_id)
            if cfg:
                max_tokens = cfg.model_context_windows.get(model_name, FALLBACK_CTX)
                multimodal = cfg.model_vision.get(model_name, False)

        return {"max_tokens": max_tokens, "multimodal": multimodal}

    def get_default_llm(
        self,
        thinking_enabled: bool = False,
        temperature: float = 0.7,
        streaming: bool = True,
        **kwargs: Any,
    ) -> BaseChatModel | None:
        """获取默认 provider 的 LLM（惰性缓存）。无可用 provider 时返回 None。

        Args:
            thinking_enabled: 是否对默认 LLM 注入 ``extra_body`` 开启思考模式。
                默认 ``False``（关闭），规避 DeepSeek 思考模式下工具调用必须完整
                回传 reasoning_content（思维链）否则 400 的问题；主对话轮次等需要
                思考模式的场景传 ``True`` 保持开启。无论厂商一律注入——OpenAI
                兼容服务端对未知的顶层 extra_body 字段通常忽略。
            temperature: LLM 采样温度，默认 0.7。
            streaming: 是否流式，默认 True。

        同一 ``(thinking_enabled, temperature, streaming)`` 的实例缓存复用；
        provider 变更（load_all）后缓存自动清空，或显式调用 :meth:`refresh_default_llm`
        立即重建。
        """
        provider = self.get_default_provider()
        if provider is None:
            return None
        key = (thinking_enabled, temperature, streaming)
        if key in self._default_llm_cache:
            return self._default_llm_cache[key]
        thinking = {"type": "enabled" if thinking_enabled else "disabled"}
        extra = dict(kwargs.get("extra_body") or {})
        extra["thinking"] = thinking
        kwargs["extra_body"] = extra
        llm = provider.create_llm(
            provider.default_model,
            temperature=temperature,
            streaming=streaming,
            **kwargs,
        )
        self._default_llm_cache[key] = llm
        return llm

    def refresh_default_llm(self, thinking_enabled: bool = False) -> BaseChatModel | None:
        """清除默认 LLM 缓存并重新构建（切换/增删 provider 后调用）。

        Args:
            thinking_enabled: 重建时采用的思考模式取值，默认 ``False``（关闭）。
        """
        self._default_llm_cache.clear()
        return self.get_default_llm(thinking_enabled=thinking_enabled)

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
        from api.providers.openai_provider import OpenAIProvider

        return OpenAIProvider(config)


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