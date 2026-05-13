"""记忆叙事模块 — 每轮对话后将裸消息送给 LLM，增量更新 MEMORY.md。"""

import asyncio
import traceback
from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

DEBUG = True  # 调试开关，排查 MEMORY.md 未更新的问题

PERSONAS_DIR = Path(__file__).resolve().parent.parent / "config" / "personas"
MEMORY_PATH = PERSONAS_DIR / "MEMORY.md"

# CRUD 工具操作的当前会话状态，每次 _consumer 迭代前重置
_current_entries: dict[str, str] = {}
_next_id: int = 1

COLD_START_SYSTEM = """你是一位"记忆叙事师"。根据对话记录，用第三人称撰写关于用户的简洁中文记忆。

你必须使用提供的工具来管理记忆：
- 先调用 read_memories 查看当前记忆（冷启动时为空）
- 使用 create_memory 逐条添加新事实
- 无需调用 update_memory 或 delete_memory（冷启动时没有旧记忆）

核心原则：
1. 只写用户明确说过的事实，绝不编造、推测或补全任何信息
2. 每条记忆一个独立事实，用 create_memory 逐条添加
3. 用户说了什么就记什么，信息少就少写，不要凑字数
4. 用第三人称自然语言描述"""

UPDATE_SYSTEM = """你是一位"记忆叙事师"。以下是当前记忆（每条带唯一ID）和一轮新对话。请对比新旧信息，更新记忆。

你必须使用提供的工具来管理记忆：
- 先调用 read_memories 查看所有当前记忆
- 新信息用 create_memory 逐条添加
- 已有信息需要修正或补充时用 update_memory（通过 ID 指定）
- 与新信息矛盾或已过时的条目用 delete_memory 删除

核心原则：
1. 只写用户明确说过的事实，绝不编造、推测或补全任何信息
2. 保留正确的已有信息；新信息优先于旧信息；矛盾时以新信息为准
3. 每条记忆一个独立事实
4. 用第三人称自然语言描述"""


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


def _parse_memory(content: str) -> tuple[dict[str, str], int]:
    """解析 MEMORY.md 文本为带自增 ID 的字典。

    返回 ({id: content}, next_id)。跳过不以 "- " 开头的行。
    """
    entries: dict[str, str] = {}
    next_id = 1
    for line in content.strip().split("\n"):
        line = line.strip()
        if line.startswith("- "):
            entries[str(next_id)] = line[2:].strip()
            next_id += 1
    return entries, next_id


def _serialize_memory(entries: dict[str, str]) -> str:
    """将 {id: content} 字典序列化为 MEMORY.md 格式。"""
    lines = [f"- {text}" for text in entries.values()]
    return "\n".join(lines) + "\n"


# ── CRUD 工具 ──────────────────────────────────────────────────

@tool
def create_memory(content: str) -> str:
    """添加一条新的记忆条目。调用后返回该条目的唯一 ID。

    Args:
        content: 记忆内容，用第三人称中文描述用户的一个事实。
    """
    global _current_entries, _next_id
    eid = str(_next_id)
    _current_entries[eid] = content
    _next_id += 1
    result = f"已创建 [{eid}]: {content}"
    if DEBUG:
        print(f"[LTM-TOOL] create_memory → [{eid}] {content[:80]}...")
    return result


@tool
def read_memories() -> str:
    """查看当前所有记忆条目及其 ID。在增删改之前必须先调用此工具了解现有条目。"""
    if not _current_entries:
        if DEBUG:
            print("[LTM-TOOL] read_memories → (空)")
        return "（暂无记忆条目）"
    lines = [f"[{eid}] {text}" for eid, text in _current_entries.items()]
    result = "\n".join(lines)
    if DEBUG:
        print(f"[LTM-TOOL] read_memories → {len(_current_entries)} 条")
    return result


@tool
def update_memory(id: str, content: str) -> str:
    """根据 ID 更新一条已有记忆。

    Args:
        id: 要更新的记忆 ID（来自 read_memories 的输出）。
        content: 更新后的完整内容。
    """
    if id not in _current_entries:
        if DEBUG:
            print(f"[LTM-TOOL] update_memory [{id}] → 错误：ID 不存在")
        return f"错误：未找到 ID 为 {id} 的记忆条目。请先调用 read_memories 确认 ID。"
    old = _current_entries[id]
    _current_entries[id] = content
    if DEBUG:
        print(f"[LTM-TOOL] update_memory [{id}] 旧→新")
    return f"已更新 [{id}]\n  旧: {old}\n  新: {content}"


@tool
def delete_memory(id: str) -> str:
    """根据 ID 删除一条记忆。

    Args:
        id: 要删除的记忆 ID（来自 read_memories 的输出）。
    """
    if id not in _current_entries:
        if DEBUG:
            print(f"[LTM-TOOL] delete_memory [{id}] → 错误：ID 不存在")
        return f"错误：未找到 ID 为 {id} 的记忆条目。请先调用 read_memories 确认 ID。"
    removed = _current_entries.pop(id)
    if DEBUG:
        print(f"[LTM-TOOL] delete_memory [{id}] 已删除")
    return f"已删除 [{id}]: {removed}"


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
        """后台消费者协程：从队列取消息，调用 CRUD Agent，写入 MEMORY.md。"""
        global _current_entries, _next_id

        while True:
            turn_messages = await self._queue.get()
            if turn_messages is None:
                if DEBUG:
                    print("[LTM-CONSUMER] 收到哨兵，即将退出")
                break

            try:
                if DEBUG:
                    print(f"\n{'='*60}")
                    print("[LTM-CONSUMER] === 新轮次开始 ===")
                    print(f"[LTM-CONSUMER] 收到 {len(turn_messages)} 条消息")

                old_narrative = self.get_narrative()
                messages_text = _format_messages(turn_messages)

                if old_narrative:
                    _current_entries, _next_id = _parse_memory(old_narrative)
                    system_prompt = UPDATE_SYSTEM
                    user_prompt = (
                        f"## 新一轮对话\n{messages_text}"
                    )
                    if DEBUG:
                        print(f"[LTM-CONSUMER] 模式: 更新 (解析到 {len(_current_entries)} 条旧记忆)")
                        for eid, text in _current_entries.items():
                            print(f"[LTM-CONSUMER]   旧 [{eid}]: {text[:60]}...")
                else:
                    _current_entries, _next_id = {}, 1
                    system_prompt = COLD_START_SYSTEM
                    user_prompt = messages_text
                    if DEBUG:
                        print("[LTM-CONSUMER] 模式: 冷启动")

                crud_tools = [create_memory, read_memories, update_memory, delete_memory]
                if DEBUG:
                    print("[LTM-CONSUMER] 构建 CRUD Agent...")

                agent = create_react_agent(
                    model=llm,
                    tools=crud_tools,
                    prompt=system_prompt,
                    checkpointer=MemorySaver(),
                )

                if DEBUG:
                    print("[LTM-CONSUMER] 调用 agent.ainvoke...")

                result = await agent.ainvoke(
                    {"messages": [HumanMessage(content=user_prompt)]},
                    config={"configurable": {"thread_id": "ltm-consumer"}},
                )

                if DEBUG:
                    msg_count = len(result.get("messages", []))
                    print(f"[LTM-CONSUMER] Agent 返回 {msg_count} 条消息")
                    # 打印最后一条非工具消息（Agent 的最终回复）
                    for m in reversed(result.get("messages", [])):
                        if hasattr(m, "content") and getattr(m, "type", "") != "tool":
                            print(f"[LTM-CONSUMER] Agent 最终回复: {str(m.content)[:200]}")
                            break
                    print(f"[LTM-CONSUMER] 操作后 _current_entries: {len(_current_entries)} 条")
                    for eid, text in _current_entries.items():
                        print(f"[LTM-CONSUMER]   新 [{eid}]: {text[:60]}...")

                new_narrative = _serialize_memory(_current_entries)
                if new_narrative.strip():
                    self._memory_path.parent.mkdir(parents=True, exist_ok=True)
                    self._memory_path.write_text(new_narrative, encoding="utf-8")
                    if DEBUG:
                        print(f"[LTM-CONSUMER] ✅ 已写入 MEMORY.md ({len(new_narrative)} 字节)")
                else:
                    if DEBUG:
                        print("[LTM-CONSUMER] ⚠️ 叙事为空，跳过写入")
            except Exception:
                if DEBUG:
                    print(f"[LTM-CONSUMER] ❌ 异常:\n{traceback.format_exc()}")
                pass
