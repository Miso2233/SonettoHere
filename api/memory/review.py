"""记忆复核登记表 —— 后台记忆写入 TECH/PROJECT/MOMENT 时的人工复核队列。

链路：

1. 同步的 CRUD 工具（跑在 LangChain 的线程池里，**无法 await**）在写入成功后
   调用 :func:`record_create`，把待复核的写入登记为「草稿」；
2. :class:`~api.memory.consumer.MemoryConsumer` 在本轮 agent 跑完后统一
   :func:`drain_drafts` 取走草稿，经 :func:`publish` 变成带 ``review_id`` 的
   待决项，再由 WebSocket 推给前端；
3. 前端用户在卡片上点「批准 / 拒绝」，WS 消息 ``memory_review_decision``
   回到 :func:`resolve`；拒绝则调用 ``mm.delete()`` 撤销该次写入。

本模块只依赖标准库与 :mod:`api.memory.theme`，**不得** import ``api.events``
（会经 ``api.events.transport`` → ``api.agent.interaction`` 形成循环依赖）。
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, TypedDict

from api.memory.theme import needs_review, theme_label
from api.utils.logger import get_logger

if TYPE_CHECKING:
    from api.memory.manager import BaseMemoryManager

_log = get_logger("ltm-review")


#: 单轮最多登记的草稿数，防止记忆 agent 疯狂创建撑爆内存。
MAX_DRAFTS: int = 64

#: 待决复核的注册表上限，超出按插入顺序淘汰。
MAX_PENDING: int = 200

#: ``resolve()`` 查不到 review_id 时的说明文案。
_EXPIRED_DETAIL: str = "该复核已失效（服务已重启或被淘汰），记忆已保留"

#: ``resolve()`` 重复调用时的说明文案。
_REPEAT_DETAIL: str = "该复核已处理过"


# ── 枚举与数据结构 ──────────────────────────────────


class ReviewKind(str, Enum):
    """复核类型。目前仅「新建」；枚举形式为未来扩展留位。"""

    CREATE = "create"


class ReviewDecision(str, Enum):
    """用户对复核卡片的决定。"""

    APPROVE = "approve"
    REJECT = "reject"


class ReviewStatus(str, Enum):
    """复核结果状态。``str`` 子类，可直接序列化为 JSON 字符串。"""

    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ERROR = "error"


class ReviewResult(TypedDict):
    """``resolve()`` 的返回值，同时作为 ``memory_review_result`` 事件的 payload。"""

    review_id: str
    """被处理的复核 ID。"""
    status: str
    """``ReviewStatus`` 的 ``value``。"""
    memory_id: str
    """涉及的记忆条目 ID。"""
    detail: str
    """面向用户的中文说明。"""


@dataclass
class ReviewDraft:
    """工具线程内登记的、尚未绑定会话的复核草稿。"""

    kind: ReviewKind
    memory_id: str
    description: str
    theme: str


@dataclass
class PendingReview:
    """已发布、等待用户决定的复核项。"""

    review_id: str
    session_id: str
    turn_id: str
    kind: ReviewKind
    memory_id: str
    description: str
    theme: str
    created_at: float
    mm: BaseMemoryManager
    """撤销时用于删除条目的记忆管理器（进程内长生命周期对象）。"""
    resolved: bool = False
    """是否已被用户决定。"""
    decision: ReviewDecision | None = None
    """首次决定；使重复调用幂等并能返回真实终态。"""


# ── 模块级状态 ──────────────────────────────────────

_drafts: list[ReviewDraft] = []
_pending: dict[str, PendingReview] = {}
_lock: threading.Lock = threading.Lock()


# ── 登记与派发 ──────────────────────────────────────


def record_create(memory_id: str, description: str, theme: str) -> None:
    """登记一条「新建记忆」复核草稿。

    由同步的 ``create_memory`` 工具在其**写入成功之后**调用，纯内存操作，
    无 IO、无 await。主题不命中 :data:`~api.memory.theme.REVIEW_THEMES`、
    或 ``memory_id`` 为空时静默跳过——复核策略集中在本函数判定，
    工具侧无需重复判断。

    Args:
        memory_id: 新建条目的 ID。
        description: 条目正文。
        theme: 条目主题 KEY。
    """
    if not memory_id or not needs_review(theme):
        return
    with _lock:
        if len(_drafts) >= MAX_DRAFTS:
            _log.warning("复核草稿已达上限 %d，丢弃本条 memory_id=%s", MAX_DRAFTS, memory_id)
            return
        _drafts.append(
            ReviewDraft(
                kind=ReviewKind.CREATE,
                memory_id=memory_id,
                description=description,
                theme=theme,
            )
        )


def drain_drafts() -> list[ReviewDraft]:
    """原子地取出并清空当前累积的全部草稿。

    取值与清空必须在同一把锁内完成：同一批工具调用会被 LangChain 用
    ``asyncio.gather`` 并发执行，分两步做会让并发线程新登记的草稿被丢弃。

    Returns:
        本轮登记的草稿列表；无草稿时为空列表。
    """
    with _lock:
        if not _drafts:
            return []
        drafts = list(_drafts)
        _drafts.clear()
        return drafts


def publish(
    draft: ReviewDraft,
    session_id: str,
    turn_id: str,
    mm: BaseMemoryManager,
) -> PendingReview:
    """为草稿分配 ``review_id``、登记进待决注册表并返回。

    Args:
        draft: 待发布的草稿。
        session_id: 目标会话 ID，用于回推事件。
        turn_id: 触发本轮记忆处理的轮次 ID，供前端定位卡片位置。
        mm: 撤销时使用的记忆管理器。

    Returns:
        已登记的待决复核项。
    """
    review = PendingReview(
        review_id=uuid.uuid4().hex,
        session_id=session_id,
        turn_id=turn_id,
        kind=draft.kind,
        memory_id=draft.memory_id,
        description=draft.description,
        theme=draft.theme,
        created_at=time.time(),
        mm=mm,
    )
    with _lock:
        _evict_locked()
        _pending[review.review_id] = review
    return review


def review_payload(review: PendingReview) -> dict[str, str]:
    """构造 ``memory_review_required`` 的 WebSocket payload。

    主题的中文标签由服务端算好一并下发（``theme_label``），避免前端重复维护映射。
    """
    return {
        "review_id": review.review_id,
        "turn_id": review.turn_id,
        "kind": review.kind.value,
        "memory_id": review.memory_id,
        "description": review.description,
        "theme": review.theme,
        "theme_label": theme_label(review.theme),
    }


def list_pending(session_id: str) -> list[PendingReview]:
    """返回指定会话中尚未被用户决定的复核项。

    供 WebSocket 重连时补推——覆盖「发布时用户恰好断开」的窗口。
    """
    with _lock:
        return [
            review
            for review in _pending.values()
            if review.session_id == session_id and not review.resolved
        ]


# ── 用户决定 ────────────────────────────────────────


def resolve(review_id: str, decision: ReviewDecision) -> ReviewResult:
    """执行用户对某条复核的决定，并返回可回推前端的处理结果。

    ``approve`` 仅把条目移出待决状态（记忆已落盘，无需额外动作）；
    ``reject`` 调用 ``mm.delete()`` 撤销这次写入。

    幂等：重复调用返回**首次决定**对应的状态，使刷新后的陈旧卡片点一下
    即可自愈到真实终态，前端无需任何特例分支。``review_id`` 不存在时
    返回 :data:`ReviewStatus.EXPIRED`，绝不静默忽略——否则前端卡片会永远
    停在「待处理」。

    Args:
        review_id: 待处理的复核 ID。
        decision: 用户的决定。

    Returns:
        处理结果（``review_id`` / ``status`` / ``memory_id`` / ``detail``）。
    """
    with _lock:
        review = _pending.get(review_id)
        if review is None:
            return ReviewResult(
                review_id=review_id,
                status=ReviewStatus.EXPIRED.value,
                memory_id="",
                detail=_EXPIRED_DETAIL,
            )
        if review.resolved:
            # 幂等：回放首次决定的终态
            status = (
                ReviewStatus.APPROVED.value
                if review.decision is ReviewDecision.APPROVE
                else ReviewStatus.REJECTED.value
            )
            return ReviewResult(
                review_id=review.review_id,
                status=status,
                memory_id=review.memory_id,
                detail=_REPEAT_DETAIL,
            )
        review.resolved = True
        review.decision = decision

    # 记忆库写入放在锁外，避免持锁做 IO
    if decision is ReviewDecision.APPROVE:
        return ReviewResult(
            review_id=review.review_id,
            status=ReviewStatus.APPROVED.value,
            memory_id=review.memory_id,
            detail="已保留",
        )

    try:
        review.mm.delete(review.memory_id)
    except ValueError:
        # 条目已被后续整理删除，撤销意图已达成
        return ReviewResult(
            review_id=review.review_id,
            status=ReviewStatus.REJECTED.value,
            memory_id=review.memory_id,
            detail="该条目已不存在（可能已被后续整理删除）",
        )
    except Exception as e:  # 撤销失败必须回执（不吞异常），故不在此处向上抛
        _log.error("撤销记忆条目失败 review_id=%s memory_id=%s: %s", review.review_id, review.memory_id, e)
        return ReviewResult(
            review_id=review.review_id,
            status=ReviewStatus.ERROR.value,
            memory_id=review.memory_id,
            detail=f"撤销失败：{e}",
        )

    # 不回带被删的记忆内容：卡片上正文本就划着删除线，重复一遍只是噪音。
    # detail 留空时前端不会渲染补充说明行。
    return ReviewResult(
        review_id=review.review_id,
        status=ReviewStatus.REJECTED.value,
        memory_id=review.memory_id,
        detail="",
    )


# ── 内部辅助 ────────────────────────────────────────


def _evict_locked() -> None:
    """在持锁状态下淘汰超额条目，为新条目腾位。

    优先逐出已决定的条目（用户已处理完、不再需要），不足时再按插入顺序
    逐出最旧的未决条目。
    """
    while len(_pending) >= MAX_PENDING:
        victim = next((rid for rid, r in _pending.items() if r.resolved), None)
        if victim is None:
            victim = next(iter(_pending), None)
        if victim is None:
            return
        _pending.pop(victim, None)
        _log.warning("复核注册表已满，淘汰 review_id=%s", victim)


def reset() -> None:
    """清空草稿与待决注册表。仅供测试与进程初始化使用。"""
    with _lock:
        _drafts.clear()
        _pending.clear()
