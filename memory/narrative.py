"""记忆叙事模块 — 每轮对话后将裸消息送给 LLM，增量更新 memory.yaml。"""

import asyncio
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from memory.memory_callback import MemoryToolCallback
from memory.memory_manager import MemoryManager


def _sanitize(text: str) -> str:
    """将多行文本折叠为单行，防止破坏 YAML 格式。"""
    return text.replace("\n", " ").replace("\r", " ")


PERSONAS_DIR = Path(__file__).resolve().parent.parent / "config" / "personas"
MEMORY_PATH = PERSONAS_DIR / "memory.yaml"

_CORE_PRINCIPLES = """核心原则：
0. 对于记忆来讲，主观印象第一，客观事实第二。科技、事实等固定的客观事实必须简洁简练，不要尝试在记忆里写大量知识性质的东西。相反地，用户的喜好等主观印象可以相对正常地描写。每个记忆条目最长不超过三句话。
1. 并不是对话里提及的每一个细节都值得记录。你被要求只记录简洁的记忆。仅关注用户的喜好、用户与助理正在做的事、困难与解决方法这些部分。其它的细节应当直接丢弃。若你看到已有记忆记录里有条目违反这一规则（如列举了某目录下的文件夹、列举了某个软件的详细用法等），应主动编辑、进行精简。
2. 只基于对话内容记录事实，不编造不推测。信息少就少写，不要凑字数。新旧矛盾时以新信息为准。
3. 每条记忆一个独立事实，每次必须提供正确的 section。
4. 用第三人称自然语言描述。
5. 禁止使用"今天""明天""昨天""下周"等相对时间词汇，必须使用绝对日期写入记忆。已提供当前日期和星期几，请自行换算。
6. 少即是多。任何条目不能过长。

反面例子：2026年6月23日，用户 和 Sonetto 讨论了用声明式 YAML 配置（类似 providers.yaml 的模式）来管理 MCP 服务器的方案，目标是实现不写代码就能添加 MCP 服务器。方案包括新建 config/mcp_servers.yaml 以及可选的 POST /api/mcp/reload 热加载端点。

**不要**把记忆写成像反面例子一样。若出现，应立即修正。

**正面例子**：2026年6月23日，用户 和 Sonetto 讨论了用 YAML 配置来管理 MCP 的方案，目标是实现不写代码就能添加 MCP 服务器。

**学习该正面例子的写法。留意其较短的句子长度和较少的技术细节。**
"""

_COLD_PREFIX = """你是一位"记忆叙事师"。根据对话记录，用第三人称撰写关于用户的简洁中文记忆。

你必须使用提供的工具来管理记忆：
- 先调用 read_memories 查看当前记忆（冷启动时为空）
- 使用 create_memory 逐条添加新事实，每次必须指定 section 参数
- 无需调用 update_memory 或 delete_memory（冷启动时没有旧记忆）

由于当前记忆为空，你必须创建新分区（1-4字中文名词）。

"""

_UPDATE_PREFIX = """你是一位"记忆叙事师"。以下是当前记忆（每条带唯一ID和分区）和一轮新对话。请对比新旧信息，更新记忆。

你必须使用提供的工具来管理记忆：
- 先调用 read_memories 查看所有当前记忆（注意每条记忆的分区）
- 新信息用 create_memory 逐条添加，每次必须指定 section 参数
- 已有信息需要修正或补充时用 update_memory（通过 ID 指定）
- 与新信息矛盾或已过时的条目用 delete_memory 删除

记忆分区：优先使用已有分区；若记忆不适合任何已有分区或用户明确要求新建，可以创建新分区（1-4字中文名词）。
对于"瞬间"分区的条目，如果内容不再有意义可以删除；对于"时效待办"，到期后务必删除。

"""

COLD_START_SYSTEM = _COLD_PREFIX + _CORE_PRINCIPLES
UPDATE_SYSTEM = _UPDATE_PREFIX + _CORE_PRINCIPLES


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


@lru_cache(maxsize=1)
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
        self._ws_registry = None

    @property
    def is_listening(self) -> bool:
        """后台消费者协程是否正在运行。"""
        return self._consumer_task is not None and not self._consumer_task.done()

    def get_narrative(self) -> str:
        """读取当前记忆叙事，不存在则返回空字符串。"""
        if not self._memory_path.exists():
            return ""
        mm = MemoryManager(yaml_file=str(self._memory_path))
        return _format_narrative(mm.show())

    def start_listening(self, llm, ws_registry=None) -> None:
        """创建 asyncio.Queue 并启动后台消费者协程。

        必须在运行中的事件循环内调用。
        """
        self._ws_registry = ws_registry
        self._queue = asyncio.Queue()
        self._consumer_task = asyncio.create_task(self._consumer(llm))

    async def send_history(
        self,
        turn_messages: list[dict],
        session_id: str | None = None,
        turn_id: str | None = None,
    ) -> None:
        """生产者：将本轮对话消息放入队列（非阻塞）。

        可附带 session_id 和 turn_id，供后台消费者关联到前端对话轮次。
        """
        if not turn_messages:
            return
        if self._queue is not None:
            await self._queue.put((session_id, turn_id, list(turn_messages)))
            print(
                f"[ltm] queue.put session={session_id} turn_id={turn_id} queue_size≈{self._queue.qsize()}"
            )
        else:
            print("[ltm] queue is None, dropping history")

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
            item = await self._queue.get()
            if item is None:
                break
            session_id, turn_id, turn_messages = item
            print(
                f"[ltm] consumer got session={session_id} turn_id={turn_id} msgs={len(turn_messages)}"
            )

            # 无论后续成功与否，先通知前端「开始处理」
            _sent_done = False
            if self._ws_registry is not None and session_id:
                ws = self._ws_registry.get(session_id)
                if ws is not None:
                    try:
                        await ws.send_json(
                            {
                                "type": "memory_start",
                                "payload": {"turn_id": turn_id or ""},
                            }
                        )
                        print(
                            f"[ltm] memory_start sent session={session_id[:8]} turn_id={turn_id[:8]}"
                        )
                    except Exception:
                        pass

            try:
                _set_current_mm(self._mm)
                items = self._mm.show()
                messages_text = _format_messages(turn_messages)

                if items:
                    system_prompt = UPDATE_SYSTEM
                    user_prompt = f"## 新一轮对话\n{messages_text}"
                else:
                    system_prompt = COLD_START_SYSTEM
                    user_prompt = messages_text

                now = datetime.now()
                weekday_cn = [
                    "星期一",
                    "星期二",
                    "星期三",
                    "星期四",
                    "星期五",
                    "星期六",
                    "星期日",
                ][now.weekday()]
                date_prefix = (
                    f"\n\n--- 会话日期: {now.strftime('%Y-%m-%d')} {weekday_cn} ---"
                )
                user_prompt = user_prompt + date_prefix

                crud_tools = [
                    create_memory,
                    read_memories,
                    update_memory,
                    delete_memory,
                    merge_memories,
                ]

                agent = create_react_agent(
                    model=llm,
                    tools=crud_tools,
                    prompt=system_prompt,
                    checkpointer=MemorySaver(),
                )

                # 创建回调：推送 CRUD 工具调用到前端对应轮次
                callbacks = []
                if self._ws_registry is not None and session_id:
                    print(
                        f"[ltm] creating MemoryToolCallback session={session_id[:8]} turn_id={turn_id[:8]}"
                    )
                    memory_cb = MemoryToolCallback(
                        self._ws_registry,
                        session_id,
                        turn_id or "",
                    )
                    callbacks.append(memory_cb)
                else:
                    print("[ltm] NO ws_registry or session_id — skip callbacks")

                print("[ltm] invoking CRUD agent...")
                await agent.ainvoke(
                    {"messages": [HumanMessage(content=user_prompt)]},
                    config={
                        "configurable": {"thread_id": "ltm-consumer"},
                        "callbacks": callbacks,
                    },
                )
                print("[ltm] CRUD agent done")

            except Exception as e:
                print(f"[ltm] CRUD agent error: {e}")
            finally:
                # 无论异常与否，都通知前端本轮记忆处理完成
                if self._ws_registry is not None and session_id:
                    ws = self._ws_registry.get(session_id)
                    if ws is not None:
                        try:
                            await ws.send_json(
                                {
                                    "type": "memory_done",
                                    "payload": {"turn_id": turn_id or ""},
                                }
                            )
                            print(
                                f"[ltm] memory_done sent session={session_id[:8]} turn_id={turn_id[:8]}"
                            )
                        except Exception as e:
                            print(f"[ltm] memory_done send error: {e}")
                    else:
                        print(
                            f"[ltm] ws_registry.get returned None for session={session_id[:8]}"
                        )
                else:
                    print("[ltm] NO ws_registry or session_id — skip memory_done")
