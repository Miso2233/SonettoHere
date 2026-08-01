"""模型元数据并发检测入口。

每新增/更新提供商时，并发执行已注册的所有 enrichment 函数。
通过 register() 扩展，核心代码无需修改（开放/封闭原则）。
"""

import asyncio
from collections.abc import Callable

from api.providers import ProviderConfig
from api.providers.manager import ProviderManager
from api.providers.model_context_windows import (
    ensure_openrouter_cache,
    fill_missing_context_windows,
)
from api.providers.vision import detect_vision_if_available
from api.utils.logger import get_logger

_log = get_logger("enrich")

_registry: list[Callable[[ProviderConfig], object]] = []


def register(func: Callable[[ProviderConfig], object]) -> None:
    """注册一个 enrichment 函数，入参为 ProviderConfig，原地修改。"""
    _registry.append(func)


# 注册内置 enrichment
register(detect_vision_if_available)
register(fill_missing_context_windows)


async def enrich_provider_config(config: ProviderConfig) -> None:
    """并发执行所有已注册的 enrichment 函数。"""
    await asyncio.gather(*(f(config) for f in _registry))


async def enrich_all_providers(manager: ProviderManager) -> int:
    """为所有已配置 provider 补充缺失的上下文窗口并持久化（启动时调用）。

    预加载 OpenRouter 缓存，逐配置补充缺失的上下文窗口值，有变更则保存。
    仅做上下文窗口填充，不含视觉检测——视觉检测在保存 provider 时由
    :func:`enrich_provider_config` 触发，启动全量执行开销过高。

    Args:
        manager: Provider 管理器，用于读取全部配置并持久化变更。

    Returns:
        本次补充的模型总数。
    """
    ensure_openrouter_cache()  # 启动预热，成功时全局仅拉取一次
    total_filled = 0
    for config in manager.list_configs():
        filled = await fill_missing_context_windows(config)
        if filled:
            manager.save_config(config)
            total_filled += filled
    if total_filled:
        _log.info("auto-filled %d model(s) from OpenRouter", total_filled)
    return total_filled