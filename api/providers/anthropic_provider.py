"""Anthropic 官方 API（含兼容代理）的 Provider 实现。"""

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from api.providers import HealthStatus, Provider

# Anthropic SDK 默认端点（路径如 /v1/messages、/v1/models 由 SDK 追加）。
# 不能省略 base_url 依赖 SDK 默认值——ChatAnthropic 与 AsyncAnthropic 都会读取
# ANTHROPIC_BASE_URL 环境变量（本机即被设为 DeepSeek 的 Anthropic 兼容代理），
# 必须显式传官方端点才能保证"留空 = 官方 API"。
DEFAULT_BASE_URL = "https://api.anthropic.com"


class AnthropicProvider(Provider):
    """适配 Anthropic 官方 API 的提供商（原生 Messages API，非 OpenAI 兼容协议）。"""

    def create_llm(self, model: str, **kwargs: Any) -> BaseChatModel:
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=model,
            api_key=self.config.api_key,
            base_url=self.config.base_url or DEFAULT_BASE_URL,
            **kwargs,
        )

    async def check_health(self) -> HealthStatus:
        import time

        from anthropic import AsyncAnthropic

        start = time.monotonic()
        try:
            client = AsyncAnthropic(
                api_key=self.config.api_key,
                base_url=self.config.base_url or DEFAULT_BASE_URL,
            )
            await client.models.list()
            elapsed = (time.monotonic() - start) * 1000
            return HealthStatus(status="ok", latency_ms=round(elapsed, 1))
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return HealthStatus(
                status="error",
                latency_ms=round(elapsed, 1),
                detail=str(exc),
            )
