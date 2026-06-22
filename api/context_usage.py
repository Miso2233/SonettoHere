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
    if not isinstance(text, str) or not text:
        return 0
    return len(_get_encoding().encode(text))


def estimate_context_usage(
    messages: list,
    system_prompt: str,
    max_tokens: int,
    model_name: str = "",
    system_prompt_parts: list[dict] | None = None,
) -> dict:
    """估算当前上下文占用的 token 数，可选返回细分数据。

    Args:
        messages: LangChain 消息列表（含 role + content）
        system_prompt: 系统提示词全文
        max_tokens: 模型上下文窗口上限
        model_name: 模型名称
        system_prompt_parts: 可选，系统提示词各部分，
            每项为 {"key": str, "label": str, "content": str}

    Returns:
        基础字段保持不变；传入 system_prompt_parts 时额外包含 breakdown。
    """
    # ── 系统提示词细分 ──
    sys_parts: list[dict] = []
    sys_total = 0
    if system_prompt_parts:
        for part in system_prompt_parts:
            t = count_tokens(part["content"])
            sys_parts.append({
                "key": part.get("key", ""),
                "label": part["label"],
                "tokens": t,
            })
            sys_total += t
    else:
        sys_total = count_tokens(system_prompt)

    # ── 对话消息细分 ──
    MSG_LABELS = {"human": "用户输入", "ai": "回复", "tool": "工具"}
    msg_buckets: dict[str, int] = {"human": 0, "ai": 0, "tool": 0}
    msg_counts: dict[str, int] = {"human": 0, "ai": 0, "tool": 0}
    total = sys_total  # 从 system prompt 开始累加

    for msg in messages:
        content = msg.content if hasattr(msg, "content") else str(msg)
        # content 可能是 list（Anthropic 多内容块格式）或 None
        if isinstance(content, list):
            parts_text = [
                b.get("text", "")
                for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            ]
            content = " ".join(parts_text)
        elif not isinstance(content, str):
            content = str(content) if content is not None else ""
        t = count_tokens(content) + 4  # ~4 tokens 消息格式化开销

        role = getattr(msg, "type", "")
        bucket = role if role in msg_buckets else "human"  # fallback
        msg_buckets[bucket] += t
        msg_counts[bucket] += 1
        total += t

    usage_percent = round(total / max_tokens * 100, 1) if max_tokens else 0.0

    result: dict = {
        "current_tokens": total,
        "max_tokens": max_tokens,
        "usage_percent": usage_percent,
        "model_name": model_name,
    }

    # 仅在提供了 parts 时附带 breakdown
    if system_prompt_parts:
        msg_parts = [
            {"key": k, "label": MSG_LABELS[k], "tokens": msg_buckets[k], "count": msg_counts[k]}
            for k in ("human", "ai", "tool")
            if msg_buckets[k] > 0
        ]
        msg_total = sum(msg_buckets.values())
        result["breakdown"] = {
            "system_prompt": {
                "total": sys_total,
                "usage_percent": round(sys_total / max_tokens * 100, 1) if max_tokens else 0.0,
                "parts": sys_parts,
            },
            "messages": {
                "total": msg_total,
                "usage_percent": round(msg_total / max_tokens * 100, 1) if max_tokens else 0.0,
                "parts": msg_parts,
            },
        }

    return result
