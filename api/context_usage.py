"""上下文窗口用量估算 — 基于 tiktoken 的 token 计数工具。"""

import tiktoken

_ENCODING = None


def _get_encoding():
    global _ENCODING
    if _ENCODING is None:
        _ENCODING = tiktoken.get_encoding("cl100k_base")
    return _ENCODING


def count_tokens(text: str) -> int:
    """返回文本的 token 数量估计值。"""
    return len(_get_encoding().encode(text))


def estimate_context_usage(
    messages: list,
    system_prompt: str,
    max_tokens: int,
    model_name: str = "",
) -> dict:
    """估算当前上下文占用的 token 数。

    Args:
        messages: LangChain 消息列表（含 role + content）
        system_prompt: 系统提示词全文
        max_tokens: 模型上下文窗口上限
        model_name: 模型名称

    Returns:
        {"current_tokens": int, "max_tokens": int, "usage_percent": float, "model_name": str}
    """
    total = count_tokens(system_prompt)
    for msg in messages:
        content = msg.content if hasattr(msg, "content") else str(msg)
        total += count_tokens(content) + 4  # ~4 tokens 消息格式化开销

    usage_percent = round(total / max_tokens * 100, 1) if max_tokens else 0.0
    return {
        "current_tokens": total,
        "max_tokens": max_tokens,
        "usage_percent": usage_percent,
        "model_name": model_name,
    }
