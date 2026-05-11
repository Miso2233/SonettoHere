"""记忆叙事模块 — 每轮对话后将裸消息送给 LLM，增量更新 MEMORY.md。"""

from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

PERSONAS_DIR = Path(__file__).resolve().parent.parent / "config" / "personas"
MEMORY_PATH = PERSONAS_DIR / "MEMORY.md"

COLD_START_SYSTEM = """你是一个记忆叙事师。根据以下用户与AI助手的对话，撰写一份关于这个用户的自然语言记忆。

要求：
1. 用第三人称描述用户
2. 涵盖：用户身份、偏好习惯、重要事件、注意事项
3. 简洁连贯，200-400字
4. 保留关键细节（地址、时间、项目名等）
5. 不确定的信息不要编造"""

UPDATE_SYSTEM = """你是一个记忆叙事师。以下是当前你对用户的记忆，以及新一轮的对话。请在现有记忆的基础上，融入新信息，写一份更新后的记忆。

要求：
1. 用第三人称描述用户
2. 涵盖：用户身份、偏好习惯、重要事件、注意事项
3. 简洁连贯，200-400字
4. 保留已有正确信息，新信息优先于旧信息
5. 如果新信息与旧记忆矛盾，以新信息为准
6. 不确定的信息不要编造"""


def get_narrative() -> str:
    """读取当前记忆叙事，不存在则返回空字符串。"""
    if MEMORY_PATH.exists():
        return MEMORY_PATH.read_text(encoding="utf-8").strip()
    return ""


def update_narrative(llm, turn_messages: list[dict]) -> None:
    """用本轮裸对话消息更新记忆叙事。

    Args:
        llm: ChatOpenAI 实例
        turn_messages: 本轮对话消息列表 [{"role": "...", "content": "..."}, ...]
    """
    if not turn_messages:
        return

    old_narrative = get_narrative()
    messages_text = _format_messages(turn_messages)

    if old_narrative:
        system_prompt = UPDATE_SYSTEM
        user_prompt = f"## 当前记忆\n{old_narrative}\n\n## 新一轮对话\n{messages_text}"
    else:
        system_prompt = COLD_START_SYSTEM
        user_prompt = messages_text

    try:
        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ])
        new_narrative = response.content.strip()
        if new_narrative:
            MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
            MEMORY_PATH.write_text(new_narrative + "\n", encoding="utf-8")
    except Exception:
        pass


def _format_messages(messages: list[dict]) -> str:
    """将消息列表格式化为可读文本。"""
    lines = []
    for m in messages:
        role = m.get("role", "unknown")
        content = str(m.get("content", ""))
        lines.append(f"[{role}]: {content}")
    return "\n".join(lines)
