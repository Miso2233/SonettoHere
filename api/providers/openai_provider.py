"""OpenAI 兼容 API 的通用 Provider 实现。"""

from langchain_core.language_models.chat_models import BaseChatModel

from api.providers import HealthStatus, Provider


class OpenAIProvider(Provider):
    """适配所有 OpenAI 兼容 API 的提供商（DeepSeek / Qwen / Kimi 等）。"""

    def create_llm(self, model: str, **kwargs) -> BaseChatModel:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            **kwargs,
        )

    async def check_health(self) -> HealthStatus:
        import time

        from openai import AsyncOpenAI

        start = time.monotonic()
        try:
            client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
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
