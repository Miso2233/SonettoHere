"""消息内容工具 — 内容展平等跨模块通用的 LangChain 消息辅助函数。"""

from typing import Any


def flatten_content(content: Any) -> str:
    """将消息 content 展平为纯文本字符串。

    当 content 为列表（多模态格式，含 image_url 等）时，
    仅提取所有 text 字段，忽略非文本块（图片 base64 等）。
    """
    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                texts.append(part.get("text", ""))
        return "\n".join(texts)
    return content if isinstance(content, str) else str(content or "")
