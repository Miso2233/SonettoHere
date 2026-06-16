"""Web API 共享资源 — LLM、系统提示词、工具集的惰性单例。"""

from agent.prompts import build_system_prompt
from tools import get_all_tools

_system_prompt: str | None = None
_tools: list | None = None


def get_llm(provider_manager=None):
    """获取 LLM。

    从 ProviderManager 中取第一个 enabled provider 创建 LLM。
    若无可用的 provider 则抛出 RuntimeError。
    LLM 配置统一由 providers.yaml 管理，不再降级到 .env。
    """
    if provider_manager is not None and provider_manager.count > 0:
        for provider in provider_manager.iter_enabled():
            return provider.create_llm(
                provider.default_model,
                temperature=0.7,
                streaming=True,
            )

    raise RuntimeError("No enabled LLM provider configured. Add one via the providers panel (/providers).")


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
