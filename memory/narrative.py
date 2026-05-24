"""记忆叙事模块 — 每轮对话后将裸消息送给 LLM，增量更新 memory.yaml。"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from memory.memory_manager import MemoryManager


def _sanitize(text: str) -> str:
    """将多行文本折叠为单行，防止破坏 YAML 格式。"""
    return text.replace("\n", " ").replace("\r", " ")

PERSONAS_DIR = Path(__file__).resolve().parent.parent / "config" / "personas"
MEMORY_PATH = PERSONAS_DIR / "memory.yaml"

COLD_START_SYSTEM = """你是一位"记忆叙事师"。根据对话记录，用第三人称撰写关于用户的简洁中文记忆。

你必须使用提供的工具来管理记忆：
- 先调用 read_memories 查看当前记忆（冷启动时为空）
- 使用 create_memory 逐条添加新事实，每次必须指定 section 参数
- 无需调用 update_memory 或 delete_memory（冷启动时没有旧记忆）

由于当前记忆为空，你必须创建新分区（1-4字中文名词）

核心原则：
1. 只写用户明确说过的事实，绝不编造、推测或补全任何信息
2. 每条记忆一个独立事实，用 create_memory 逐条添加，每次必须提供正确的 section
3. 用户说了什么就记什么，信息少就少写，不要凑字数
4. 用第三人称自然语言描述
5. 禁止使用"今天""明天""昨天""下周"等相对时间词汇，必须使用绝对日期写入记忆。已提供当前时间、日期和星期几，请自行换算。"""

UPDATE_SYSTEM = """你是一位"记忆叙事师"。以下是当前记忆（每条带唯一ID和分区）和一轮新对话。请对比新旧信息，更新记忆。

你必须使用提供的工具来管理记忆：
- 先调用 read_memories 查看所有当前记忆（注意每条记忆的分区）
- 新信息用 create_memory 逐条添加，每次必须指定 section 参数
- 已有信息需要修正或补充时用 update_memory（通过 ID 指定）
- 与新信息矛盾或已过时的条目用 delete_memory 删除

记忆分区（优先使用已有分区；若记忆不适合任何已有分区或用户明确要求新建，可以创建新分区（1-4字中文名词））

核心原则：
1. 只写用户明确说过的事实，绝不编造、推测或补全任何信息
2. 保留正确的已有信息；新信息优先于旧信息；矛盾时以新信息为准
3. 每条记忆一个独立事实，每次 create_memory 必须提供正确的 section
4. 用第三人称自然语言描述
5. 对于"瞬间"分区的条目，如果内容不再有意义可以删除；对于"时效待办"，到期后务必删除
6. 禁止使用"今天""明天""昨天""下周"等相对时间词汇，必须使用绝对日期写入记忆。已提供当前时间、日期和星期几，请自行换算。"""


# ── 模块级 MemoryManager 引用 ──────────────────────────────

_current_mm: Optional[MemoryManager] = None


def _set_current_mm(mm: Optional[MemoryManager]) -> None:
    global _current_mm
    _current_mm = mm


# ── 格式化辅助 ──────────────────────────────────────────────


def _format_narrative(items: list[dict]) -> str:
    """将 MemoryManager.show() 的输出格式化为人类可读的长记忆叙事文本。"""
    if not items:
        return ""
    by_theme: dict[str, list[dict]] = {}
    theme_order: list[str] = []
    for item in items:
        theme = item["theme"]
        by_theme.setdefault(theme, []).append(item)
        if theme not in theme_order:
            theme_order.append(theme)
    lines = ["# 长期记忆索引"]
    for theme in theme_order:
        lines.append(f"- [{theme}](#{theme})")
    lines.extend(["", "---", ""])
    for theme in theme_order:
        lines.append(f"## {theme}")
        for item in by_theme[theme]:
            lines.append(f"- {item['description']}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _format_entries_for_tool(items: list[dict]) -> str:
    """为 read_memories 工具格式化条目（按 theme 分组，带 ID）。"""
    if not items:
        return "（暂无记忆条目）"
    by_theme: dict[str, list[dict]] = {}
    theme_order: list[str] = []
    for item in items:
        theme = item["theme"]
        by_theme.setdefault(theme, []).append(item)
        if theme not in theme_order:
            theme_order.append(theme)
    lines = []
    for theme in theme_order:
        lines.append(f"## {theme}")
        for item in by_theme[theme]:
            lines.append(f"  [{item['id']}] {item['description']}")
        lines.append("")
    return "\n".join(lines).strip()


def get_narrative() -> str:
    """读取当前记忆叙事，不存在则返回空字符串。"""
    if not MEMORY_PATH.exists():
        return ""
    mm = MemoryManager(yaml_file=str(MEMORY_PATH))
    return _format_narrative(mm.show())


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


# ── CRUD 工具（模块级 @tool，委托给 _current_mm）─────────────────


@tool
def create_memory(content: str, section: str) -> str:
    """添加一条新的记忆条目到指定分区。调用后返回该条目的唯一 ID。

    Args:
        content: 记忆内容，用第三人称中文描述用户的一个事实。
        section: 记忆分区。优先使用已有分区；若不适合任何已有分区或用户明确要求新建，可创建新分区（1-4字中文）：
            - "身份"（用户的基本身份信息：教育、职业、家乡等）
            - "音乐"（虚拟歌手、声库、歌曲、专辑、创作者）
            - "品味"（电影、美食、UP主、品牌偏好等）
            - "地点与路径"（具体地点和文件系统路径）
            - "瞬间"（即时观察和感受：天气、正在做的事、念头）
            - "时效待办"（有截止日期的事项：作业、预约、考试）
    """
    content = _sanitize(content)
    if _current_mm is None:
        return "错误：记忆管理器未初始化。"
    new_id = _current_mm.add(description=content, theme=section)
    return f"已创建 [{new_id}] ({section}): {content}"


@tool
def read_memories() -> str:
    """查看当前所有记忆条目及其 ID 和分区。在增删改之前必须先调用此工具了解现有条目。"""
    if _current_mm is None:
        return "（暂无记忆条目）"
    result = _format_entries_for_tool(_current_mm.show())
    return result


@tool
def update_memory(id: str, content: str, reason: str) -> str:
    """根据 ID 更新一条已有记忆。

    Args:
        id: 要更新的记忆 ID（来自 read_memories 的输出）。
        content: 更新后的完整内容。
        reason: 修改原因，说明为什么要更新这条记忆。
    """
    content = _sanitize(content)
    if _current_mm is None:
        return "错误：记忆管理器未初始化。"
    try:
        _current_mm.update(id, reason=reason, new_description=content)
    except ValueError:
        return f"错误：未找到 ID 为 {id} 的记忆条目。请先调用 read_memories 确认 ID。"
    return f"已更新 [{id}]: {content}"


@tool
def delete_memory(id: str, reason: str) -> str:
    """根据 ID 删除一条记忆。

    Args:
        id: 要删除的记忆 ID（来自 read_memories 的输出）。
        reason: 删除原因，说明为什么要删除这条记忆。
    """
    if _current_mm is None:
        return "错误：记忆管理器未初始化。"
    try:
        removed = _current_mm.delete(id)
    except ValueError:
        return f"错误：未找到 ID 为 {id} 的记忆条目。请先调用 read_memories 确认 ID。"
    return f"已删除 [{id}]: {removed}"


@tool
def merge_memories(id1: str, id2: str, content: str, section: str, reason: str) -> str:
    """将两条相似记忆合并为一条，id1 保留、id2 被删除，同时保留两者的修改历史。

    当两条记忆描述同一事物（如分散的身份信息、同一首歌在不同分区的重复条目）
    时使用，避免碎片化。

    Args:
        id1: 合并后保留的记忆 ID（主条目）。
        id2: 合并后将被删除的记忆 ID（从条目）。
        content: 合并后的完整记忆内容，涵盖两条原条目的信息。
        section: 合并后的记忆分区。
        reason: 合并原因，说明为什么这两条记忆需要合并。
    """
    if _current_mm is None:
        return "错误：记忆管理器未初始化。"
    try:
        _current_mm.merge(id1, id2, content, section, reason)
    except ValueError:
        return f"错误：未找到 ID 为 {id1} 或 {id2} 的记忆条目。请先调用 read_memories 确认 ID。"
    return f"已合并 [{id2}] → [{id1}] ({section}): {content}"


# ── LongTermMemoryInterface ───────────────────────────────────


class LongTermMemoryInterface:
    """异步管线：逐轮对话消息 → asyncio.Queue → 后台 LLM 总结 → memory.yaml 写入。

    用法::

        ltm = LongTermMemoryInterface("/path/to/memory.yaml")
        ltm.start_listening(llm)          # 启动后台消费者
        await ltm.send_history(messages)  # 投放本轮对话（非阻塞）
        await ltm.stop_listening()        # 排空队列并停止
    """

    def __init__(self, memory_path: str | Path) -> None:
        self._memory_path = Path(memory_path)
        self._mm = MemoryManager(yaml_file=str(self._memory_path))
        self._queue: asyncio.Queue | None = None
        self._consumer_task: asyncio.Task | None = None

    def get_narrative(self) -> str:
        """读取当前记忆叙事，不存在则返回空字符串。"""
        if not self._memory_path.exists():
            return ""
        mm = MemoryManager(yaml_file=str(self._memory_path))
        return _format_narrative(mm.show())

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
        """后台消费者协程：从队列取消息，调用 CRUD Agent，写入 memory.yaml。"""

        while True:
            turn_messages = await self._queue.get()
            if turn_messages is None:
                break

            try:
                _set_current_mm(self._mm)
                items = self._mm.show()
                messages_text = _format_messages(turn_messages)

                if items:
                    system_prompt = UPDATE_SYSTEM
                    user_prompt = (
                        f"## 新一轮对话\n{messages_text}"
                    )
                else:
                    system_prompt = COLD_START_SYSTEM
                    user_prompt = messages_text

                now = datetime.now()
                weekday_cn = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][now.weekday()]
                time_suffix = (
                    f"\n\n## 当前时间\n"
                    f"日期: {now.strftime('%Y-%m-%d')}  {weekday_cn}\n"
                    f"时间: {now.strftime('%H:%M:%S')}"
                )
                user_prompt = user_prompt + time_suffix

                crud_tools = [create_memory, read_memories, update_memory, delete_memory, merge_memories]

                agent = create_react_agent(
                    model=llm,
                    tools=crud_tools,
                    prompt=system_prompt,
                    checkpointer=MemorySaver(),
                )

                result = await agent.ainvoke(
                    {"messages": [HumanMessage(content=user_prompt)]},
                    config={"configurable": {"thread_id": "ltm-consumer"}},
                )

            except Exception:
                pass
