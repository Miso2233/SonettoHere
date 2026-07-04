"""知名模型的上下文窗口默认值。

三层优先级（高 → 低）：
1. config/model_context_windows.yaml（用户自定义覆盖）
2. 本文件的 MODEL_CONTEXT_WINDOWS（硬编码保底表）
3. DEFAULT_WINDOW（通用兜底值）

get_context_window() — 按模型名匹配，支持子串匹配。
"""
from pathlib import Path

# 硬编码保底映射表（按匹配优先级从高到低排列）
# key 是模型名的小写子串，value 是上下文窗口 token 数
MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    # ── OpenAI ──
    "gpt-4.1": 1_047_576,
    "gpt-4o": 128_000,
    "gpt-4": 128_000,
    "o3": 200_000,
    "o4-mini": 200_000,
    "o1": 200_000,
    # ── Anthropic ──
    "claude": 200_000,
    # ── DeepSeek ──
    "deepseek-v4": 1_000_000,
    "deepseek-v3": 128_000,
    "deepseek-r1": 128_000,
    "deepseek": 128_000,
    # ── Google ──
    "gemini-2.5-pro": 1_048_576,
    "gemini-2.5-flash": 1_048_576,
    "gemini-2.0": 1_048_576,
    "gemini-1.5": 2_000_000,
    "gemini": 1_048_576,
    # ── Meta ──
    "llama-4-scout": 10_000_000,
    "llama-4": 1_000_000,
    "llama-3": 128_000,
    "llama": 128_000,
    # ── Mistral ──
    "mistral-large": 128_000,
    "mistral-small": 128_000,
    "mistral": 128_000,
    # ── Qwen ──
    "qwen": 128_000,
    # ── Cohere ──
    "command-a": 256_000,
    "command-r": 128_000,
    "command": 128_000,
    # ── xAI ──
    "grok": 200_000,
}

# 通用兜底值（没有任何匹配时使用）
DEFAULT_WINDOW: int = 128_000

# 用户自定义覆盖文件的路径
CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "model_context_windows.yaml"


def _load_overrides() -> dict[str, int]:
    """从 YAML 配置文件加载用户自定义覆盖。"""
    import yaml
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        overrides = data.get("overrides", {})
        return {k: int(v) for k, v in overrides.items()}
    except Exception:
        return {}


def get_context_window(model_name: str) -> int:
    """按模型名查找上下文窗口。

    匹配优先级：
    1. YAML 配置文件中的精确模型名匹配
    2. 硬编码表中的子串匹配（如 "gpt-4o" 匹配 "gpt-4o"）
    3. 通用兜底值
    """
    model_lower = model_name.lower()

    # 1. 精确匹配（YAML 配置优先）
    overrides = _load_overrides()
    if model_lower in overrides:
        return overrides[model_lower]

    # 2. 子串匹配（硬编码表）
    for key, value in MODEL_CONTEXT_WINDOWS.items():
        if key in model_lower:
            return value

    # 3. 兜底
    return DEFAULT_WINDOW
