"""从 OpenRouter API 拉取模型上下文窗口数据。

设计：OpenRouter 是唯一数据源，对每个模型做子串匹配。
如果 OpenRouter 中没有该模型的数据，则不返回（用户手动配置）。
无硬编码表、无本地覆盖、无兜底值。
"""

import json
import urllib.request
import urllib.error

from api.providers import ProviderConfig
from api.utils.logger import get_logger

_log = get_logger("context-window")

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/models"

_OPENROUTER_CACHE: dict[str, int] | None = None


def _fetch_openrouter_models() -> dict[str, int]:
    """从 OpenRouter /api/v1/models 拉取全量模型上下文窗口。

    Returns:
        {模型ID小写: context_length, ...}。
        失败时返回空字典。
    """
    try:
        req = urllib.request.Request(
            OPENROUTER_API_URL,
            headers={"User-Agent": "SonettoHere/1.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        result: dict[str, int] = {}
        for m in data.get("data", []):
            ctx = m.get("context_length")
            if ctx and isinstance(ctx, (int, float)):
                result[m["id"].lower()] = int(ctx)
        return result
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError,
            OSError, TimeoutError):
        return {}


def ensure_openrouter_cache() -> dict[str, int]:
    """惰性加载 OpenRouter 缓存（成功时全局仅拉取一次）。"""
    global _OPENROUTER_CACHE
    if _OPENROUTER_CACHE is None:
        data = _fetch_openrouter_models()
        if data:
            _OPENROUTER_CACHE = data
            _log.info("loaded %d model(s) from OpenRouter", len(data))
    return _OPENROUTER_CACHE or {}


def lookup_context_window(model_name: str) -> int | None:
    """在 OpenRouter 数据中查找模型的上下文窗口值。

    匹配策略（按优先级）：
    1. 精确匹配：模型名与 OpenRouter ID 完全相同
    2. 后缀匹配：OpenRouter ID 以 ``/模型名`` 结尾
    3. 子串匹配：OpenRouter ID 包含模型名

    Returns:
        context_window token 数，未找到时返回 None。
    """
    or_data = ensure_openrouter_cache()
    if not or_data:
        return None

    model_lower = model_name.lower()

    # 1. 精确匹配
    if model_lower in or_data:
        return or_data[model_lower]

    # 2. 后缀匹配：OpenRouter ID 以 /model_name 结尾
    suffix = f"/{model_lower}"
    for or_id, ctx in or_data.items():
        if or_id.endswith(suffix):
            return ctx

    # 3. 子串匹配：OpenRouter ID 包含 model_name
    for or_id, ctx in or_data.items():
        if model_lower in or_id:
            return ctx

    return None

async def fill_missing_context_windows(config: ProviderConfig) -> int:
    """为 config.models 中缺失上下文窗口值的模型从 OpenRouter 补充。

    仅补充 config.model_context_windows 中不存在的模型，已有值不受影响。

    Returns:
        本次补充的模型数量。
    """
    or_data = ensure_openrouter_cache()
    if not or_data:
        return 0

    filled = 0
    for model in config.models:
        if model not in config.model_context_windows:
            ctx = lookup_context_window(model)
            if ctx:
                config.model_context_windows[model] = ctx
                filled += 1
    return filled
