"""Provider 抽象基类与类型定义。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel

FALLBACK_CTX: int = 128_000


@dataclass
class ProviderConfig:
    """单个 LLM 提供商的配置，对应 providers.yaml 中的一项。"""

    id: str
    provider_type: str  # 如 "openai"、"openrouter"、"deepseek" 等 OpenAI 兼容 API
    label: str
    api_key: str
    base_url: str
    models: list[str] = field(default_factory=list)
    enabled: bool = True
    model_vision: dict[str, bool] = field(default_factory=dict)
    is_default_provider: bool = False
    default_model: str | None = None
    model_context_windows: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        if not d.get("model_vision"):
            del d["model_vision"]
        if d.get("is_default_provider") is None:
            d.pop("is_default_provider", None)
        if d.get("default_model") is None:
            d.pop("default_model", None)
        if not d.get("model_context_windows"):
            del d["model_context_windows"]
        return d


@dataclass
class HealthStatus:
    """提供商健康检查结果。"""

    status: Literal["ok", "error"]
    latency_ms: float | None = None
    detail: str | None = None


class Provider(ABC):
    """所有 LLM 提供商必须实现的接口。"""

    def __init__(self, config: ProviderConfig):
        self.config = config

    @property
    def provider_name(self) -> str:
        return self.config.id

    @property
    def default_model(self) -> str:
        if self.config.default_model and self.config.default_model in self.config.models:
            return self.config.default_model
        return self.config.models[0] if self.config.models else ""

    @property
    def available_models(self) -> list[str]:
        return self.config.models

    @abstractmethod
    def create_llm(self, model: str, **kwargs) -> BaseChatModel:
        """根据指定模型名创建 LangChain ChatModel 实例。"""
        ...

    @abstractmethod
    async def check_health(self) -> HealthStatus:
        """验证提供商 API 连接是否正常。"""
        ...
