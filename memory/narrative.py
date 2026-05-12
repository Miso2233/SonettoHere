"""记忆叙事模块 — 每轮对话后将裸消息送给 LLM，增量更新 MEMORY.md。"""

import asyncio
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

PERSONAS_DIR = Path(__file__).resolve().parent.parent / "config" / "personas"
MEMORY_PATH = PERSONAS_DIR / "MEMORY.md"

COLD_START_SYSTEM = """你是一个记忆叙事师。以下是用户与AI助手的一段对话。请仅根据对话中用户明确表达的信息，撰写一份关于这个用户的简洁记忆。

核心原则——违反将导致严重错误：
1. 只写用户明确说过的事实。绝不编造、推测或补全任何用户未提及的信息。
2. 用户说了什么就记什么，信息少就写短，不要为凑字数而生造内容。
3. 用第三人称自然语言描述，不超过 400 字。

可涵盖的方面（有则写，无则跳过，不要强行填满）：
- 用户身份（职业、专业、角色等）
- 偏好习惯（沟通风格、工具偏好等）
- 重要事件或项目
- 注意事项"""

UPDATE_SYSTEM = """你是一个记忆叙事师。以下是当前你对用户的记忆，以及新一轮的对话。请在现有记忆的基础上，融入新信息，写一份更新后的记忆。

核心原则——违反将导致严重错误：
1. 只写用户明确说过的事实。绝不编造、推测或补全任何用户未提及的信息。
2. 保留已有正确信息；新信息优先于旧信息；矛盾时以新信息为准。
3. 用第三人称自然语言描述，不超过 400 字。

可涵盖的方面（有则写，无则跳过，不要强行填满）：
- 用户身份（职业、专业、角色等）
- 偏好习惯（沟通风格、工具偏好等）
- 重要事件或项目
- 注意事项"""


def get_narrative() -> str:
    """读取当前记忆叙事，不存在则返回空字符串。"""
    if MEMORY_PATH.exists():
        return MEMORY_PATH.read_text(encoding="utf-8").strip()
    return ""


def _format_messages(messages: list[dict]) -> str:
    """将消息列表格式化为可读文本，过滤掉工具输出避免幻觉。"""
    lines = []
    for m in messages:
        role = m.get("role", "unknown")
        if role == "tool":
            continue
        content = str(m.get("content", ""))
        lines.append(f"[{role}]: {content}")
    return "\n".join(lines)


class LongTermMemoryInterface:
    """异步管线：逐轮对话消息 → asyncio.Queue → 后台 LLM 总结 → MEMORY.md 写入。

    用法::

        ltm = LongTermMemoryInterface("/path/to/MEMORY.md")
        ltm.start_listening(llm)          # 启动后台消费者
        await ltm.send_history(messages)  # 投放本轮对话（非阻塞）
        await ltm.stop_listening()        # 排空队列并停止
    """

    def __init__(self, memory_path: str | Path) -> None:
        self._memory_path = Path(memory_path)
        self._queue: asyncio.Queue | None = None
        self._consumer_task: asyncio.Task | None = None

    def get_narrative(self) -> str:
        """读取当前记忆叙事，不存在则返回空字符串。"""
        if self._memory_path.exists():
            return self._memory_path.read_text(encoding="utf-8").strip()
        return ""

    def start_listening(self, llm) -> None:
        """创建 asyncio.Queue 并启动后台消费者协程。

        必须在运行中的事件循环内调用。
        """
        self._queue = asyncio.Queue()
        self._consumer_task = asyncio.create_task(self._consumer(llm))

    async def send_history(self, turn_messages: list[dict]) -> None:
        """生产者：将本轮对话消息放入队列（非阻塞）。"""
        if not turn_messages:
            return
        if self._queue is not None:
            await self._queue.put(list(turn_messages))

    async def stop_listening(self) -> None:
        """发送 None 哨兵并等待消费者排空队列。"""
        if self._queue is not None:
            await self._queue.put(None)
            await self._consumer_task
            self._queue = None
            self._consumer_task = None

    async def _consumer(self, llm) -> None:
        """后台消费者协程：从队列取消息，调用 ainvoke，写入 MEMORY.md。"""
        while True:
            turn_messages = await self._queue.get()
            if turn_messages is None:
                break

            try:
                old_narrative = self.get_narrative()
                messages_text = _format_messages(turn_messages)

                if old_narrative:
                    system_prompt = UPDATE_SYSTEM
                    user_prompt = (
                        f"## 当前记忆\n{old_narrative}\n\n"
                        f"## 新一轮对话\n{messages_text}"
                    )
                else:
                    system_prompt = COLD_START_SYSTEM
                    user_prompt = messages_text

                response = await llm.ainvoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ])
                new_narrative = response.content.strip()
                if new_narrative:
                    self._memory_path.parent.mkdir(parents=True, exist_ok=True)
                    self._memory_path.write_text(
                        new_narrative + "\n", encoding="utf-8"
                    )
            except Exception:
                pass
