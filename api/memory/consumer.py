"""记忆消费者 — 后台 CRUD Agent 管线，逐轮消费对话并写入 memory_v6.yaml。"""

from __future__ import annotations

import asyncio
import functools
import time
from datetime import datetime
from typing import Any

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver

from api.events import MemorySender
from api.memory import review
from api.memory.callback import MemoryToolCallback
from api.memory.manager import BaseMemoryManager, MAX_DESC_LENGTH
from api.memory.theme import THEME_LABELS, require_theme, theme_display
from api.utils.logger import get_logger

_log = get_logger("ltm")

#: 单轮记忆处理的看门狗超时（秒）。
#: 取值只作兜底而非性能目标——正常一轮（含多轮工具调用）在十秒量级，
#: 一旦超过这个数说明上游 LLM 已挂死。超时后放弃本轮剩余处理并照常发出
#: 收尾事件，保证前端不会永久停在「处理中」。
CONSUMER_TIMEOUT_S: float = 180.0


# ── 提示词常量 ──────────────────────────────────────

_CORE_PRINCIPLES = """核心原则：
0. 对于记忆来讲，主观印象第一，客观事实第二。科技、事实等固定的客观事实必须简洁简练，不要尝试在记忆里写大量知识性质的东西。相反地，用户的喜好等主观印象可以正常地描写。每个记忆条目最长不超过三句话。
1. 并不是对话里提及的每一个细节都值得记录。你被要求只记录简洁的记忆。仅关注用户的喜好、用户与助理正在做的事、困难与解决方法这些部分。其它的细节应当直接丢弃。若你看到已有记忆记录里有条目违反这一规则（如列举了某目录下的文件夹、列举了某个软件的详细用法等），应主动编辑、进行精简。
2. 只基于对话内容记录事实，不编造不推测。信息少就少写，不要凑字数。新旧矛盾时以新信息为准。
3. 每条记忆一个独立事实，有且只有一个主题，每次必须提供合法的主题 KEY。
4. 用第三人称自然语言描述。
5. 禁止使用"今天""明天""昨天""下周"等相对时间词汇，必须使用绝对日期写入记忆。已提供当前日期和星期几，请自行换算。
6. 少即是多。任何条目不能过长。每个记忆描述**不得超过 75 个中文字符（含标点）**。超过 75 字的记忆创建、更新或合并请求会被系统自动驳回。
7. 若内容超过 75 字，应主动拆分：保留核心事实，将次要信息另起一条独立条目。

反面例子：2026年6月23日，用户 和 Sonetto 讨论了用声明式 YAML 配置（类似 providers.yaml 的模式）来管理 MCP 服务器的方案，目标是实现不写代码就能添加 MCP 服务器。方案包括新建 config/mcp_servers.yaml 以及可选的 POST /api/mcp/reload 热加载端点。

**不要**把记忆写成像反面例子一样。若出现，应立即修正。

**正面例子**：2026年6月23日，用户 和 Sonetto 讨论了用 YAML 配置来管理 MCP 的方案，目标是实现不写代码就能添加 MCP 服务器。

**学习该正面例子的写法。留意其较短的句子长度和较少的技术细节。**
"""

_THEME_BLOCK = "\n".join(f"- {key}（{label}）" for key, label in THEME_LABELS.items())

_THEME_RULE = (
    "记忆主题为 V6 固定九大枚举，每条记忆有且只有一个主题：\n"
    + _THEME_BLOCK
    + "\ncreate_memory / merge_memories 的 section 参数必须填写上述英文 KEY"
    "（不带中文括号）；禁止自创或沿用 V5 的中文主题名（如 身份、项目、瞬间 等）。"
)

_COLD_PREFIX = """你是一位"记忆叙事师"。根据对话记录，用第三人称撰写关于用户的简洁中文记忆。

你必须使用提供的工具来管理记忆：
- 先调用 read_memories 查看当前记忆（冷启动时为空）
- 使用 create_memory 逐条添加新事实，每次必须指定 section 参数
- 无需调用 update_memory 或 delete_memory（冷启动时没有旧记忆）

由于当前记忆为空（冷启动），请直接使用下方固定的九大主题 KEY 创建分区，不得新建主题。

"""

_UPDATE_PREFIX = """你是一位"记忆叙事师"。以下是当前记忆（每条带唯一ID和分区）和一轮新对话。请对比新旧信息，更新记忆。

你必须使用提供的工具来管理记忆：
- 先调用 read_memories 查看所有当前记忆（注意每条记忆的分区）
- 新信息用 create_memory 逐条添加，每次必须指定 section 参数
- 已有信息需要修正或补充时用 update_memory（通过 ID 指定）
- 与新信息矛盾或已过时的条目用 delete_memory 删除
- 两条记忆相关且适合长期互相引用（不宜合并）时，用 link_memories 建立双向关联
- 新记忆若明显属于某条已有记忆的同一系列，可在 create_memory 的 related 参数传入该已有记忆的 ID，创建时即直接建立关联（无需再单独调 link_memories）

记忆分区：必须使用下方固定的九大主题 KEY，不得新建分区。
生命周期：TODO（计划目标承诺）到期后务必删除；MOMENT（事件与经历）若为一次性事件且已失去意义，可删除或精简。

"""

COLD_START_SYSTEM = _COLD_PREFIX + _CORE_PRINCIPLES + "\n" + _THEME_RULE
UPDATE_SYSTEM = _UPDATE_PREFIX + _CORE_PRINCIPLES + "\n" + _THEME_RULE


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
        lines.append(f"## {theme_display(theme)}")
        for item in by_theme[theme]:
            lines.append(f"  [{item['id']}] {item['description']}")
        lines.append("")
    return "\n".join(lines).strip()


# ── CRUD 工具 ───────────────────────────────────────


@tool
@_require_mm
def create_memory(content: str, section: str, related: list[str] | None = None) -> str:
    """添加一条新的记忆条目到指定分区。调用后返回该条目的唯一 ID。

    若新记忆明显属于某个/某些已有记忆的同一系列（同一主题、同一偏好、
    同一项目不同阶段等），可在 related 传入那些已存在记忆的 ID，创建时
    即与它们建立双向关联（无需再单独调 link_memories）。

    Args:
        content: 记忆内容，用第三人称中文描述用户的一个事实。
        section: 记忆分区主题 KEY，必须且只能取以下九种之一（不得自定义）：
            - "USER"（用户档案）：教育、职业、家乡、称呼等基础身份
            - "PREFERENCE"（用户喜好）：口味、兴趣、审美偏好
            - "PROJECT"（学业与创作产出）：学业、笔记、CTF、博客等产出与进度
            - "PATH"（文件与配置路径）：文件/工具/配置的本地路径
            - "LOCATION"（现实地理地点）：现实中人/物的地理位置
            - "TODO"（计划目标承诺）：有截止时间的计划、目标、承诺
            - "TECH"（技术事实与结论）：技术结论、事实、方案定论
            - "SELF"（Sonetto与SonettoHere）：关于 Sonetto / SonettoHere 自身
            - "MOMENT"（事件与经历）：一次性的具体事件、见闻、经历
        related: 可选的、已存在记忆的 ID 列表，用于创建时直接建立双向关联。
    """
    content = _sanitize(content)
    if len(content) > MAX_DESC_LENGTH:
        return (
            f"驳回：记忆内容超过 {MAX_DESC_LENGTH} 字限制（当前 {len(content)} 字），"
            f"请精简至 {MAX_DESC_LENGTH} 字以内，避免列举；或拆分为多条独立条目。"
        )
    try:
        new_id = _current_mm.add(description=content, theme=section, related=related)
    except ValueError as e:
        return f"驳回：{e}"
    # TECH/PROJECT/MOMENT 主题的写入需要用户复核；由 consumer 在本轮结束后统一发布
    review.record_create(new_id, content, section)
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
    """根据 ID 更新一条已有记忆的内容。

    Args:
        id: 要更新的记忆 ID（来自 read_memories 的输出）。
        content: 更新后的完整内容。
        reason: 修改原因，说明为什么要更新这条记忆（仅作说明，不写入）。
    """
    content = _sanitize(content)
    if len(content) > MAX_DESC_LENGTH:
        return (
            f"驳回：更新后的记忆内容超过 {MAX_DESC_LENGTH} 字限制（当前 {len(content)} 字），"
            f"请精简至 {MAX_DESC_LENGTH} 字以内，避免列举；或拆分为多条独立条目。"
        )
    try:
        _current_mm.update(id, reason=reason, new_description=content)
    except ValueError:
        return f"错误：未找到 ID 为 {id} 的记忆条目。请先调用 read_memories 确认 ID。"
    return f"已更新 [{id}]: {content}"


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
    """将两条相似记忆合并为一条，id1 保留、id2 被删除。

    当两条记忆描述同一事物（如分散的身份信息、同一首歌在不同分区的重复条目）
    时使用，避免碎片化。两条记忆的 related 关联会合并，id2 从其他记忆的
    related 中重定向到 id1。

    Args:
        id1: 合并后保留的记忆 ID（主条目）。
        id2: 合并后将被删除的记忆 ID（从条目）。
        content: 合并后的完整记忆内容，涵盖两条原条目的信息。
        section: 合并后的记忆分区主题 KEY，同 create_memory 的 section 说明（九种之一，不得自定义）。
        reason: 合并原因，说明为什么这两条记忆需要合并。
    """
    try:
        require_theme(section, who="merge_memories(section)")
    except ValueError as e:
        return f"驳回：{e}"
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
def link_memories(id1: str, id2: str) -> str:
    """在两条记忆之间建立双向关联（related 图边），用于日后关联检索。

    当两条记忆内容相关但不适合合并（例如分属不同主题却指向同一事物、
    同一偏好的多次记录、一条事件的上下文背景等）时，用此工具把它们的
    ID 关联起来。关联是双向且去重的（A↔B）。
    先调用 read_memories 拿到待关联条目的 ID。

    Args:
        id1: 第一条记忆 ID。
        id2: 第二条记忆 ID。
    """
    try:
        _current_mm.link(id1, id2)
    except ValueError as e:
        return f"错误：{e}"
    return f"已关联 [{id1}] ↔ [{id2}]"


# ── 消费者 ──────────────────────────────────────────


class MemoryConsumer:
    """后台消费一轮对话：WebSocket 通知 → CRUD Agent → memory_v6.yaml 写入。"""

    def __init__(self, llm: BaseChatModel | None) -> None:
        self._llm = llm

    async def consume(
        self,
        session_id: str | None,
        turn_id: str,
        turn_messages: list[dict[str, str]],
    ) -> None:
        """消费一轮对话。非阻塞——Agent 执行在内部 await。"""
        _t0 = time.perf_counter()
        _log.info(
            "consumer got session=%s turn_id=%s msgs=%d",
            session_id, turn_id, len(turn_messages),
        )

        # 上一轮若异常退出，草稿会滞留到本轮，必须先丢弃，避免跨轮串号
        if review.drain_drafts():
            _log.warning("丢弃上一轮残留的复核草稿 session=%s", session_id)

        # 通知前端开始处理。sender 绑定 session_id，每次发送现取当前连接，
        # 因此本轮的收尾事件不会被中途的重连丢掉（详见 WsTransport.from_session_id）。
        sender: MemorySender | None = None
        if session_id:
            sender = MemorySender.from_session_id(session_id)
            await sender.memory_start(turn_id or "")

        try:
            if self._llm is None:
                _log.warning("no LLM available — skipping memory update")
                return

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
                delete_memory, merge_memories, link_memories,
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

            # 看门狗：agent 若因上游 LLM 挂死而无限期不返回，收尾事件（含
            # memory_done）就永远不会发出，前端会永久停在「处理中」。
            # 超时即放弃本轮剩余处理——已落盘的记忆与已登记的复核照常发布。
            await asyncio.wait_for(
                agent.ainvoke(
                    {"messages": [HumanMessage(content=user_prompt)]},
                    config={
                        "configurable": {"thread_id": "ltm-consumer"},
                        "callbacks": callbacks,
                    },
                ),
                CONSUMER_TIMEOUT_S,
            )

        except TimeoutError:
            _log.error(
                "记忆 agent 超时（>%ds），放弃本轮剩余处理 turn_id=%s",
                CONSUMER_TIMEOUT_S, turn_id,
            )
        except Exception as e:
            _log.error("CRUD agent error: %s", e)
        finally:
            # 必须在 finally 里发布：agent 中途报错时工具可能已写入记忆库，
            # 这些条目同样需要用户复核，不能因为异常就丢掉卡片。
            cards = 0
            try:
                cards = await self._publish_reviews(sender, session_id, turn_id)
            except Exception as e:
                # 兜底：发布环节自身出意外（如取草稿时抛）也不得连带跳过
                # memory_done——收尾事件一旦缺席，前端就永久停在「处理中」，
                # 且没有任何后续事件能把它解开。循环内的推送失败已由
                # _publish_reviews 内部消化，这里覆盖的是它之外的部分。
                _log.error("发布复核卡片失败 turn_id=%s: %r", turn_id, e, exc_info=True)
            if sender is not None:
                await sender.memory_done(turn_id or "")
            # 每轮一行汇总：出问题时凭这一行即可判断「consumer 是否跑完」。
            _log.info(
                "本轮记忆处理结束 session=%s turn_id=%s 耗时=%.1fs 复核卡片=%d",
                session_id, turn_id, time.perf_counter() - _t0, cards,
            )

    @staticmethod
    async def _publish_reviews(
        sender: MemorySender | None,
        session_id: str | None,
        turn_id: str | None,
    ) -> int:
        """发布本轮登记的复核草稿并推送给前端。

        缺任一发送条件时直接丢弃草稿：前端靠 ``turn_id`` 定位卡片，
        空 ``turn_id`` 永远匹配不到轮次，注册只会留下拿不到的孤儿条目。

        Args:
            sender: 目标会话的事件发送器；为 None 表示前端不可达。
            session_id: 目标会话 ID。
            turn_id: 触发本轮的轮次 ID。

        Returns:
            已发布的复核卡片数量（供调用方汇总日志）。
        """
        drafts = review.drain_drafts()
        if not drafts:
            return 0
        if sender is None or not session_id or not turn_id or _current_mm is None:
            _log.warning("复核草稿无法关联到前端，丢弃 %d 条 session=%s", len(drafts), session_id)
            return 0
        published = 0
        try:
            for draft in drafts:
                pending = review.publish(draft, session_id, turn_id, _current_mm)
                await sender.memory_review_required(review.review_payload(pending))
                published += 1
                _log.info(
                    "复核卡片已发布 review_id=%s memory_id=%s theme=%s turn_id=%s",
                    pending.review_id, pending.memory_id, pending.theme, turn_id,
                )
        except Exception as e:
            # 推送失败不能掀翻后台消费者协程；未送达的复核仍留在注册表，
            # 前端重连时由 websocket_chat 的补推兜底。
            _log.error("发布复核卡片失败: %s", e)
        return published
