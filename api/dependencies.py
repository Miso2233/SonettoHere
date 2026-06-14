"""Web API 共享资源 — LLM、系统提示词、工具集的惰性单例。"""

from langchain_openai import ChatOpenAI

from agent.prompts import build_system_prompt
from config.settings import get_settings
from tools import get_all_tools

_system_prompt: str | None = None
_tools: list | None = None


def get_llm(provider_manager=None):
    """获取 LLM。

    优先使用 ProviderManager 的第一个 enabled provider，
    若无则退化到 .env 配置（首次启动 / 未配置提供商时的向后兼容）。
    """
    if provider_manager is not None and provider_manager.count > 0:
        for provider in provider_manager.iter_enabled():
            return provider.create_llm(
                provider.default_model,
                temperature=0.7,
                streaming=True,
            )

    # env fallback
    settings = get_settings()
    return ChatOpenAI(
        model=settings.model_name or "deepseek-v4-flash",
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=0.7,
        streaming=True,
        extra_body={"thinking": {"type": "disabled"}},
    )


def get_system_prompt() -> str:
    global _system_prompt
    if _system_prompt is None:
        _system_prompt = build_system_prompt()
    return _system_prompt


def get_tools() -> list:
    global _tools
    if _tools is None:
        _tools = get_all_tools()
    return _tools
