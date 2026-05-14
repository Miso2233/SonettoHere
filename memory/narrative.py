"""记忆叙事模块 — 每轮对话后将裸消息送给 LLM，增量更新 MEMORY.md。"""

import asyncio
import traceback
from datetime import datetime
from pathlib import Path

import yaml
from filelock import FileLock
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

DEBUG = False  # 调试开关，排查 MEMORY.md 未更新的问题


def _sanitize(text: str) -> str:
    """将多行文本折叠为单行，防止破坏 YAML/Markdown 行格式。"""
    return text.replace("\n", " ").replace("\r", " ")

DEFAULT_SECTION = "身份"

PERSONAS_DIR = Path(__file__).resolve().parent.parent / "config" / "personas"
MEMORY_PATH = PERSONAS_DIR / "MEMORY.md"
LOG_PATH = PERSONAS_DIR / "memory_operations.yaml"

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
4. 用第三人称自然语言描述"""

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
5. 对于"瞬间"分区的条目，如果内容不再有意义可以删除；对于"时效待办"，到期后务必删除"""


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


# ── MemorySerializer ──────────────────────────────────────────


class MemorySerializer:
    """MEMORY.md 分区格式 ↔ 条目字典 双向转换。"""

    @staticmethod
    def parse(content: str) -> tuple[dict[str, dict[str, str]], int]:
        """解析分区格式 MEMORY.md 为 {id: {section, content}} 字典。

        返回 ({id: {section, content}}, next_id)。
        跳过 TOC、---、HTML 注释、### 子标题和非 "- " 行。
        """
        entries: dict[str, dict[str, str]] = {}
        next_id = 1
        current_section: str | None = None
        for line in content.strip().split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("# ") or stripped.startswith("---"):
                continue
            if stripped.startswith("## "):
                section_name = stripped[3:].strip()
                if "<!--" in section_name:
                    section_name = section_name.split("<!--")[0].strip()
                current_section = section_name
            elif stripped.startswith("### "):
                pass
            elif stripped.startswith("- ") and current_section is not None:
                entries[str(next_id)] = {
                    "section": current_section,
                    "content": stripped[2:].strip(),
                }
                next_id += 1
        return entries, next_id

    @staticmethod
    def _section_order(entries: dict[str, dict[str, str]]) -> list[str]:
        """按条目 ID 顺序返回 section 首次出现的顺序。"""
        seen: list[str] = []
        for eid in sorted(entries.keys(), key=int):
            sec = entries[eid]["section"]
            if sec not in seen:
                seen.append(sec)
        return seen

    @staticmethod
    def serialize(entries: dict[str, dict[str, str]]) -> str:
        """将 {id: {section, content}} 序列化为带 TOC 的分区 MEMORY.md。"""
        if not entries:
            return "\n"
        by_section: dict[str, list[str]] = {}
        for entry in entries.values():
            sec = entry.get("section", DEFAULT_SECTION)
            by_section.setdefault(sec, []).append(entry["content"])

        section_order = MemorySerializer._section_order(entries)

        lines = ["# 长期记忆索引"]
        for section in section_order:
            lines.append(f"- [{section}](#{section})")
        lines.append("")
        lines.append("---")
        lines.append("")

        for section in section_order:
            lines.append(f"## {section}")
            for content in by_section[section]:
                lines.append(f"- {content}")
            lines.append("")
        return "\n".join(lines) + "\n"


# ── MemoryLogger ──────────────────────────────────────────────


class MemoryLogger:
    """YAML 操作日志记录器（线程/进程安全）。"""

    _lock = FileLock(str(LOG_PATH) + ".lock")

    @staticmethod
    def _sanitize_params(params: dict) -> dict:
        """递归清理参数中所有字符串的换行符。"""
        result = {}
        for k, v in params.items():
            if isinstance(v, str):
                result[k] = _sanitize(v)
            elif isinstance(v, dict):
                result[k] = MemoryLogger._sanitize_params(v)
            else:
                result[k] = v
        return result

    @staticmethod
    def log(operation: str, params: dict) -> None:
        """追加一条操作记录到 YAML 日志文件。"""
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "operation": operation,
            "params": MemoryLogger._sanitize_params(params),
        }
        with MemoryLogger._lock:
            if LOG_PATH.exists():
                try:
                    existing = yaml.safe_load(LOG_PATH.read_text(encoding="utf-8")) or []
                except yaml.YAMLError:
                    existing = []
            else:
                existing = []
            existing.append(entry)
            LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            LOG_PATH.write_text(
                yaml.safe_dump(existing, allow_unicode=True), encoding="utf-8"
            )


# ── MemoryStore（单例）────────────────────────────────────────


class MemoryStore:
    """记忆条目存储器（单例）。

    持有当前会话的条目字典和自增 ID 计数器，提供 CRUD 操作。
    """

    _instance: "MemoryStore | None" = None

    def __new__(cls) -> "MemoryStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self.entries: dict[str, dict[str, str]] = {}
            self.next_id: int = 1

    def reset(self) -> None:
        """重置为初始状态。"""
        self.entries.clear()
        self.next_id = 1

    def load(self, content: str) -> None:
        """从 MEMORY.md 文本解析并加载条目。"""
        self.entries, self.next_id = MemorySerializer.parse(content)

    def create(self, content: str, section: str = DEFAULT_SECTION) -> str:
        """添加一条记忆条目到指定分区，返回结果消息。"""
        content = _sanitize(content)
        if not section.strip():
            section = DEFAULT_SECTION
        eid = str(self.next_id)
        self.entries[eid] = {"section": section, "content": content}
        self.next_id += 1
        return f"已创建 [{eid}] ({section}): {content}"

    def read_all(self) -> str:
        """返回所有条目的格式化文本，按分区归类。"""
        if not self.entries:
            return "（暂无记忆条目）"
        by_section: dict[str, list[tuple[str, str]]] = {}
        for eid, entry in self.entries.items():
            sec = entry.get("section", DEFAULT_SECTION)
            by_section.setdefault(sec, []).append((eid, entry["content"]))
        lines = []
        for section in MemorySerializer._section_order(self.entries):
            if section in by_section:
                lines.append(f"## {section}")
                for eid, content in by_section[section]:
                    lines.append(f"  [{eid}] {content}")
                lines.append("")
        return "\n".join(lines).strip()

    def update(self, id: str, content: str) -> str:
        """根据 ID 更新一条条目，返回结果消息。"""
        content = _sanitize(content)
        if id not in self.entries:
            return (
                f"错误：未找到 ID 为 {id} 的记忆条目。"
                "请先调用 read_memories 确认 ID。"
            )
        old = self.entries[id]["content"]
        self.entries[id]["content"] = content
        return f"已更新 [{id}]\n  旧: {old}\n  新: {content}"

    def delete(self, id: str) -> str:
        """根据 ID 删除一条条目，返回结果消息。"""
        if id not in self.entries:
            return (
                f"错误：未找到 ID 为 {id} 的记忆条目。"
                "请先调用 read_memories 确认 ID。"
            )
        removed = self.entries.pop(id)["content"]
        return f"已删除 [{id}]: {removed}"

    def serialize(self) -> str:
        """将当前条目序列化为 MEMORY.md 格式。"""
        return MemorySerializer.serialize(self.entries)


# ── CRUD 工具（模块级 @tool，委托给 MemoryStore 单例）───────


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
    store = MemoryStore()
    result = store.create(content, section)
    MemoryLogger.log("create_memory", {"content": content, "section": section})
    if DEBUG:
        eid = str(store.next_id - 1)
        print(f"[LTM-TOOL] create_memory → [{eid}] ({section}) {content[:80]}...")
    return result


@tool
def read_memories() -> str:
    """查看当前所有记忆条目及其 ID 和分区。在增删改之前必须先调用此工具了解现有条目。"""
    store = MemoryStore()
    result = store.read_all()
    if DEBUG:
        print(f"[LTM-TOOL] read_memories → {len(store.entries)} 条")
    return result


@tool
def update_memory(id: str, content: str, reason: str, origin_content: str) -> str:
    """根据 ID 更新一条已有记忆。

    Args:
        id: 要更新的记忆 ID（来自 read_memories 的输出）。
        content: 更新后的完整内容。
        reason: 修改原因，说明为什么要更新这条记忆。
        origin_content: 修改前的原始内容，必须与 read_memories 中该 ID 对应的内容完全一致。
    """
    store = MemoryStore()
    if id not in store.entries:
        if DEBUG:
            print(f"[LTM-TOOL] update_memory [{id}] → 错误：ID 不存在")
        return f"错误：未找到 ID 为 {id} 的记忆条目。请先调用 read_memories 确认 ID。"
    result = store.update(id, content)
    MemoryLogger.log("update_memory", {
        "content": content,
        "reason": reason,
        "origin_content": origin_content,
    })
    if DEBUG:
        print(f"[LTM-TOOL] update_memory [{id}] 旧→新 | 原因: {reason[:60]}")
    return result


@tool
def delete_memory(id: str, reason: str, origin_content: str) -> str:
    """根据 ID 删除一条记忆。

    Args:
        id: 要删除的记忆 ID（来自 read_memories 的输出）。
        reason: 删除原因，说明为什么要删除这条记忆。
        origin_content: 删除前的原始内容，必须与 read_memories 中该 ID 对应的内容完全一致。
    """
    store = MemoryStore()
    if id not in store.entries:
        if DEBUG:
            print(f"[LTM-TOOL] delete_memory [{id}] → 错误：ID 不存在")
        return f"错误：未找到 ID 为 {id} 的记忆条目。请先调用 read_memories 确认 ID。"
    result = store.delete(id)
    MemoryLogger.log("delete_memory", {
        "reason": reason,
        "origin_content": origin_content,
    })
    if DEBUG:
        print(f"[LTM-TOOL] delete_memory [{id}] 已删除 | 原因: {reason[:60]}")
    return result


# ── LongTermMemoryInterface ───────────────────────────────────


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
        store = MemoryStore()

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
                    store.load(old_narrative)
                    system_prompt = UPDATE_SYSTEM
                    user_prompt = (
                        f"## 新一轮对话\n{messages_text}"
                    )
                    if DEBUG:
                        print(f"[LTM-CONSUMER] 模式: 更新 (解析到 {len(store.entries)} 条旧记忆)")
                        for eid, entry in store.entries.items():
                            print(f"[LTM-CONSUMER]   旧 [{eid}] ({entry['section']}): {entry['content'][:60]}...")
                else:
                    store.reset()
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
                    for m in reversed(result.get("messages", [])):
                        if hasattr(m, "content") and getattr(m, "type", "") != "tool":
                            print(f"[LTM-CONSUMER] Agent 最终回复: {str(m.content)[:200]}")
                            break
                    print(f"[LTM-CONSUMER] 操作后 entries: {len(store.entries)} 条")
                    for eid, entry in store.entries.items():
                        print(f"[LTM-CONSUMER]   新 [{eid}] ({entry['section']}): {entry['content'][:60]}...")

                new_narrative = store.serialize()
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
