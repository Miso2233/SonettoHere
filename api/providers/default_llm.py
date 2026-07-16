"""默认 LLM 实例管理 — 模块级惰性缓存，替代 app.state.default_llm。

用法
----
在 lifespan 中初始化：
    from api.providers.default_llm import init_provider_manager
    init_provider_manager(provider_manager)

消费方直接获取：
    from api.providers.default_llm import get_default_llm
    llm = get_default_llm()
"""

from functools import lru_cache

from api.providers.manager import ProviderManager

_provider_manager: ProviderManager | None = None


def init_provider_manager(mgr: ProviderManager) -> None:
    """在 lifespan 中由 server.py 调用，注入 ProviderManager 实例。"""
    global _provider_manager
    _provider_manager = mgr


@lru_cache(maxsize=1)
def _build():
    """内部：从 ProviderManager 构建默认 LLM 实例。"""
    if _provider_manager is None:
        return None
    return _provider_manager.get_default_llm(temperature=0.7, streaming=True)


def get_default_llm():
    """获取当前默认 LLM 实例（惰性缓存）。

    首次调用时从 ProviderManager 构建并缓存，
    后续返回缓存实例。切换 provider 后调用 refresh_default_llm() 清除缓存。
    """
    return _build()


def refresh_default_llm():
    """清除缓存并重新构建，返回新 LLM 实例。

    当用户切换默认 provider 或添加/删除 provider 后调用。
    """
    _build.cache_clear()
    return _build()
