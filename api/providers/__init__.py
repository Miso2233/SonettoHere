"""Provider 抽象基类与类型定义。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict, field
from typing import Literal

from langchain_core.language_models.chat_models import BaseChatModel


@dataclass
class ProviderConfig:
    """单个 LLM 提供商的配置，对应 providers.yaml 中的一项。"""

    id: str
    provider_type: str  # "openai" — 目前仅此一种
    label: str
    api_key: str
    base_url: str
    models: list[str] = field(default_factory=list)
    enabled: bool = True
    context_window: int = 256_000

    def to_dict(self) -> dict:
        return asdict(self)


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
