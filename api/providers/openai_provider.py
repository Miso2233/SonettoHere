"""OpenAI 兼容 API 的通用 Provider 实现。"""

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from api.providers import HealthStatus, Provider


class OpenAIProvider(Provider):
    """适配所有 OpenAI 兼容 API 的提供商（DeepSeek / Qwen / Kimi 等）。"""

    def create_llm(self, model: str, **kwargs: Any) -> BaseChatModel:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=model,
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            **kwargs,
        )

    def apply_thinking(self, kwargs: dict, enabled: bool) -> dict:
        """OpenAI 兼容提供商通过 ``extra_body.thinking`` 开启/关闭思考模式。"""
        thinking = {"type": "enabled" if enabled else "disabled"}
        extra = dict(kwargs.get("extra_body") or {})
        extra["thinking"] = thinking
        kwargs["extra_body"] = extra
        return kwargs

    async def check_health(self) -> HealthStatus:
        import asyncio
        import time

        start = time.monotonic()
        try:
            async with asyncio.timeout(10):
                client = self._async_client()
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

    async def list_models(self) -> list[str]:
        client = self._async_client()
        models = await client.models.list()
        return sorted(m.id for m in models.data)

    def _async_client(self) -> Any:
        from openai import AsyncOpenAI

        return AsyncOpenAI(
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            timeout=10,
        )
