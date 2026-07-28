"""记忆消费者 — 后台 CRUD Agent 管线，逐轮消费对话并写入 memory.yaml。"""

from __future__ import annotations

import functools
from datetime import datetime
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver

from api.events import MemorySender
from api.memory.callback import MemoryToolCallback
from api.memory.manager import BaseMemoryManager, MAX_DESC_LENGTH
from api.utils.logger import get_logger

_log = get_logger("ltm")


# ── 提示词常量 ──────────────────────────────────────

_CORE_PRINCIPLES = """核心原则：
0. 对于记忆来讲，主观印象第一，客观事实第二。科技、事实等固定的客观事实必须简洁简练，不要尝试在记忆里写大量知识性质的东西。相反地，用户的喜好等主观印象可以正常地描写。每个记忆条目最长不超过三句话。
1. 并不是对话里提及的每一个细节都值得记录。你被要求只记录简洁的记忆。仅关注用户的喜好、用户与助理正在做的事、困难与解决方法这些部分。其它的细节应当直接丢弃。若你看到已有记忆记录里有条目违反这一规则（如列举了某目录下的文件夹、列举了某个软件的详细用法等），应主动编辑、进行精简。
2. 只基于对话内容记录事实，不编造不推测。信息少就少写，不要凑字数。新旧矛盾时以新信息为准。
3. 每条记忆一个独立事实，每次必须提供正确的 section。
4. 用第三人称自然语言描述。
5. 禁止使用"今天""明天""昨天""下周"等相对时间词汇，必须使用绝对日期写入记忆。已提供当前日期和星期几，请自行换算。
6. 少即是多。任何条目不能过长。每个记忆描述**不得超过 75 个中文字符（含标点）**。超过 75 字的记忆创建、更新或合并请求会被系统自动驳回。
7. 若内容超过 75 字，应主动拆分：保留核心事实，将次要信息另起一条独立条目。

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


# ── 模块级 MemoryManager 引用 ──────────────────────

_current_mm: BaseMemoryManager | None = None


def set_current_mm(mm: BaseMemoryManager | None) -> None:
    global _current_mm
    _current_mm = mm


# ── 辅助函数 ────────────────────────────────────────


def _sanitize(text: str) -> str:
    """将多行文本折叠为单行，防止破坏 YAML 格式。"""
    return text.replace("\n", " ").replace("\r", " ")


def _require_mm(func):
    """装饰器：确保 _current_mm 已初始化，否则返回错误消息。"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if _current_mm is None:
            return "错误：记忆管理器未初始化。"
        return func(*args, **kwargs)
    return wrapper


def _format_messages(messages: list[dict[str, str]]) -> str:
    """将消息列表格式化为可读文本，过滤掉工具输出避免幻觉。"""
    lines = []
    for m in messages:
        role = m.get("role", "unknown")
        if role == "tool":
            continue
        content = str(m.get("content", ""))
        lines.append(f"[{role}]: {content}")
    return "\n".join(lines)


def _format_entries_for_tool(items: list[dict[str, str]]) -> str:
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


# ── CRUD 工具 ───────────────────────────────────────


@tool
@_require_mm
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
    if len(content) > MAX_DESC_LENGTH:
        return (
            f"驳回：记忆内容超过 {MAX_DESC_LENGTH} 字限制（当前 {len(content)} 字），"
            f"请精简至 {MAX_DESC_LENGTH} 字以内，避免列举；或拆分为多条独立条目。"
        )
    new_id = _current_mm.add(description=content, theme=section)
    return f"已创建 [{new_id}] ({section}): {content}"


@tool
@_require_mm
def read_memories() -> str:
    """查看当前所有记忆条目及其 ID 和分区。在增删改之前必须先调用此工具了解现有条目。"""
    result = _format_entries_for_tool(_current_mm.show())
    return result


@tool
@_require_mm
def update_memory(id: str, content: str, reason: str) -> str:
    """根据 ID 更新一条已有记忆。更新成功后会自动增加该记忆的引用计数（hit），表示该记忆被重新关注。

    Args:
        id: 要更新的记忆 ID（来自 read_memories 的输出）。
        content: 更新后的完整内容。
        reason: 修改原因，说明为什么要更新这条记忆。
    """
    content = _sanitize(content)
    if len(content) > MAX_DESC_LENGTH:
        return (
            f"驳回：更新后的记忆内容超过 {MAX_DESC_LENGTH} 字限制（当前 {len(content)} 字），"
            f"请精简至 {MAX_DESC_LENGTH} 字以内，避免列举；或拆分为多条独立条目。"
        )
    try:
        _current_mm.update(id, reason=reason, new_description=content)
        new_hit = _current_mm.hit(id)
    except ValueError:
        return f"错误：未找到 ID 为 {id} 的记忆条目。请先调用 read_memories 确认 ID。"
    return f"已更新 [{id}]: {content}（hit {new_hit}）"


@tool
@_require_mm
def delete_memory(id: str, reason: str) -> str:
    """根据 ID 删除一条记忆。

    Args:
        id: 要删除的记忆 ID（来自 read_memories 的输出）。
        reason: 删除原因，说明为什么要删除这条记忆。
    """
    try:
        removed = _current_mm.delete(id)
    except ValueError:
        return f"错误：未找到 ID 为 {id} 的记忆条目。请先调用 read_memories 确认 ID。"
    return f"已删除 [{id}]: {removed}（原因：{reason}）"


@tool
@_require_mm
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
    if len(content) > MAX_DESC_LENGTH:
        return (
            f"驳回：合并后的记忆内容超过 {MAX_DESC_LENGTH} 字限制（当前 {len(content)} 字），"
            f"请精简至 {MAX_DESC_LENGTH} 字以内，避免列举；或保留两条各自独立。"
        )
    try:
        _current_mm.merge(id1, id2, content, section, reason)
    except ValueError:
        return f"错误：未找到 ID 为 {id1} 或 {id2} 的记忆条目。请先调用 read_memories 确认 ID。"
    return f"已合并 [{id2}] → [{id1}] ({section}): {content}"


@tool
@_require_mm
def hit_memory(id: str) -> str:
    """标记一条记忆被引用/点击一次，增加其 hit 计数。

    当记忆被引用（如被用于回答用户问题或被关联到对话）且没有对被引用记忆进行Update时调用此工具标记。

    Args:
        id: 要标记的记忆 ID（来自 read_memories 的输出）。
    """
    try:
        new_count = _current_mm.hit(id)
    except ValueError:
        return f"错误：未找到 ID 为 {id} 的记忆条目。请先调用 read_memories 确认 ID。"
    return f"已标记记忆 [{id}]，累计点击 {new_count} 次"


# ── 消费者 ──────────────────────────────────────────


class MemoryConsumer:
    """后台消费一轮对话：WebSocket 通知 → CRUD Agent → memory.yaml 写入。"""

    def __init__(self, llm: BaseChatModel | None) -> None:
        self._llm = llm

    async def consume(
        self,
        session_id: str | None,
        turn_id: str,
        turn_messages: list[dict[str, str]],
    ) -> None:
        """消费一轮对话。非阻塞——Agent 执行在内部 await。"""
        _log.info(
            "consumer got session=%s turn_id=%s msgs=%d",
            session_id, turn_id, len(turn_messages),
        )

        # 通知前端开始处理
        sender: MemorySender | None = None
        if session_id:
            sender = MemorySender.from_session_id(session_id)
            if sender is not None:
                await sender.memory_start(turn_id or "")

        if self._llm is None:
            _log.warning("no LLM available — skipping memory update")
            if sender is not None:
                await sender.memory_done(turn_id or "")
            return

        try:
            items = _current_mm.show()
            messages_text = _format_messages(turn_messages)

            if items:
                system_prompt = UPDATE_SYSTEM
                user_prompt = f"## 新一轮对话\n{messages_text}"
            else:
                system_prompt = COLD_START_SYSTEM
                user_prompt = messages_text

            now = datetime.now()
            weekday_cn = [
                "星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日",
            ][now.weekday()]
            user_prompt += f"\n\n--- 会话日期: {now.strftime('%Y-%m-%d')} {weekday_cn} ---"

            crud_tools = [
                create_memory, read_memories, update_memory,
                delete_memory, merge_memories, hit_memory,
            ]

            agent = create_agent(
                model=self._llm,
                tools=crud_tools,
                system_prompt=system_prompt,
                checkpointer=MemorySaver(),
            )

            callbacks: list[MemoryToolCallback] = []
            if session_id:
                callbacks.append(MemoryToolCallback(session_id, turn_id or ""))

            await agent.ainvoke(
                {"messages": [HumanMessage(content=user_prompt)]},
                config={
                    "configurable": {"thread_id": "ltm-consumer"},
                    "callbacks": callbacks,
                },
            )

        except Exception as e:
            _log.error("CRUD agent error: %s", e)
        finally:
            if sender is not None:
                await sender.memory_done(turn_id or "")