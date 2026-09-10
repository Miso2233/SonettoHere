"""api.memory.review 测试 —— 记忆写入的复核登记表与撤销机制。

覆盖三层：
1. 登记层：record_create 的主题过滤、上限、drain_drafts 的原子取出；
2. 决定层：publish / resolve 的撤销与幂等；
3. 派发层：MemoryConsumer 在 finally 中发布草稿（含 agent 异常路径）。
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import yaml

import api.memory.consumer as consumer
import api.memory.review as review
from api.memory.manager import YamlMemoryManager
from api.memory.review import (
    MAX_DRAFTS,
    MAX_PENDING,
    ReviewDecision,
    ReviewDraft,
    ReviewKind,
    ReviewStatus,
)
from api.memory.theme import THEME_LABELS

# ── 测试辅助 ──────────────────────────────────────────────────


#: 需复核的三主题；独立于实现写死，防止跟着实现一起漂移。
REVIEW_THEME_KEYS = {"TECH", "PROJECT", "MOMENT"}


def _draft(
    memory_id: str = "a1",
    theme: str = "TECH",
    description: str = "某条技术结论。",
) -> ReviewDraft:
    """构造一条「新建」复核草稿。"""
    return ReviewDraft(
        kind=ReviewKind.CREATE,
        memory_id=memory_id,
        description=description,
        theme=theme,
    )


def _make_mm(tmp_path: Path) -> YamlMemoryManager:
    """创建 YAML 记忆管理器并注册为当前管理器。"""
    mm = YamlMemoryManager(yaml_file=str(tmp_path / "memory.yaml"))
    consumer.set_current_mm(mm)
    return mm


def _load_items(tmp_path: Path) -> dict[str, Any]:
    """直接读 YAML 文件，拿到含 related 的原始条目（mm.show() 不含 related）。"""
    return yaml.safe_load((tmp_path / "memory.yaml").read_text(encoding="utf-8")) or {}


def _fake_agent(
    setup: Callable[[], None] | None = None,
    raise_exc: BaseException | None = None,
) -> MagicMock:
    """构造 mock agent。

    setup 在 ainvoke **期间**执行，用于模拟「Agent 调用了 create_memory 工具」——
    草稿必须在 consume() 开始之后才登记，否则会被当成上一轮残留而清掉。
    raise_exc 非空时在 setup 之后抛异常，模拟「工具已写盘但 LLM 报错」。
    """

    async def fake_ainvoke(_input: object, config: dict[str, Any] | None = None) -> dict[str, Any]:
        if setup is not None:
            setup()
        if raise_exc is not None:
            raise raise_exc
        return {"messages": []}

    agent = MagicMock()
    agent.ainvoke = AsyncMock(side_effect=fake_ainvoke)
    return agent


@pytest.fixture
def sender_spy(monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], MagicMock]:
    """打桩 MemorySender.from_session_id，返回 (调用顺序记录, 假 sender)。

    记录的是方法名，用于断言 memory_review_required 早于 memory_done。
    """
    calls: list[str] = []
    sender = MagicMock()
    sender.memory_start = AsyncMock(
        side_effect=lambda *a, **k: calls.append("memory_start")
    )
    sender.memory_done = AsyncMock(
        side_effect=lambda *a, **k: calls.append("memory_done")
    )
    sender.memory_review_required = AsyncMock(
        side_effect=lambda payload: calls.append(f"review:{payload['memory_id']}")
    )
    monkeypatch.setattr(
        consumer.MemorySender,
        "from_session_id",
        staticmethod(lambda _sid: sender),
    )
    return calls, sender


# ── 登记层 ────────────────────────────────────────────────────


class TestRecordAndDrain:
    """record_create / drain_drafts 的登记与原子取出。"""

    def setup_method(self) -> None:
        review.reset()

    def teardown_method(self) -> None:
        review.reset()

    @pytest.mark.parametrize("key", list(THEME_LABELS))
    def test_registers_iff_needs_review(self, key: str) -> None:
        """草稿条数严格等于 needs_review(theme)：三主题登记，其余六主题跳过。"""
        review.record_create("a1", "内容。", key)
        expected = 1 if key in REVIEW_THEME_KEYS else 0
        assert len(review.drain_drafts()) == expected

    def test_empty_memory_id_skipped(self) -> None:
        review.record_create("", "内容。", "TECH")
        assert review.drain_drafts() == []

    def test_drain_is_destructive(self) -> None:
        review.record_create("a1", "内容。", "TECH")
        assert len(review.drain_drafts()) == 1
        assert review.drain_drafts() == []

    def test_max_drafts_cap(self) -> None:
        """超过 MAX_DRAFTS 的登记被丢弃，不撑爆内存。"""
        for i in range(MAX_DRAFTS + 10):
            review.record_create(f"id{i}", "内容。", "TECH")
        assert len(review.drain_drafts()) == MAX_DRAFTS

    def test_reset_clears_everything(self) -> None:
        review.record_create("a1", "内容。", "TECH")
        review.reset()
        assert review.drain_drafts() == []


# ── 决定层 ────────────────────────────────────────────────────


class TestPublishAndResolve:
    """publish / review_payload / resolve 的发布与决定执行。"""

    def setup_method(self) -> None:
        review.reset()

    def teardown_method(self) -> None:
        review.reset()

    def test_payload_shape(self, tmp_path: Path) -> None:
        mm = _make_mm(tmp_path)
        pending = review.publish(_draft(), "sess", "turn-1", mm)
        payload = review.review_payload(pending)
        assert payload == {
            "review_id": pending.review_id,
            "turn_id": "turn-1",
            "kind": "create",
            "memory_id": "a1",
            "description": "某条技术结论。",
            "theme": "TECH",
            "theme_label": "技术事实与结论",
        }

    def test_approve_keeps_memory(self, tmp_path: Path) -> None:
        mm = _make_mm(tmp_path)
        mid = mm.add(description="待复核。", theme="TECH")
        pending = review.publish(_draft(memory_id=mid), "s", "t", mm)

        result = review.resolve(pending.review_id, ReviewDecision.APPROVE)

        assert result["status"] == ReviewStatus.APPROVED.value
        assert [i["id"] for i in mm.show()] == [mid]
        assert review.list_pending("s") == []

    def test_reject_deletes_memory_once(self, tmp_path: Path) -> None:
        mm = _make_mm(tmp_path)
        spy = MagicMock(wraps=mm)
        mid = mm.add(description="待复核。", theme="TECH")
        pending = review.publish(_draft(memory_id=mid), "s", "t", spy)

        result = review.resolve(pending.review_id, ReviewDecision.REJECT)

        assert result["status"] == ReviewStatus.REJECTED.value
        # 不回带被删的内容：卡片正文已划着删除线，重复一遍只是噪音
        assert result["detail"] == ""
        spy.delete.assert_called_once_with(mid)
        assert mm.show() == []

    def test_resolve_is_idempotent(self, tmp_path: Path) -> None:
        """重复决定回放首次终态，且绝不二次删除。"""
        mm = _make_mm(tmp_path)
        spy = MagicMock(wraps=mm)
        mid = mm.add(description="待复核。", theme="TECH")
        pending = review.publish(_draft(memory_id=mid), "s", "t", spy)

        first = review.resolve(pending.review_id, ReviewDecision.REJECT)
        second = review.resolve(pending.review_id, ReviewDecision.APPROVE)

        assert first["status"] == ReviewStatus.REJECTED.value
        assert second["status"] == ReviewStatus.REJECTED.value
        spy.delete.assert_called_once_with(mid)

    def test_reject_missing_memory_still_rejected(self, tmp_path: Path) -> None:
        """条目已被后续整理删掉时，撤销意图仍算达成。"""
        mm = _make_mm(tmp_path)
        pending = review.publish(_draft(memory_id="ghost"), "s", "t", mm)

        result = review.resolve(pending.review_id, ReviewDecision.REJECT)

        assert result["status"] == ReviewStatus.REJECTED.value
        assert "已不存在" in result["detail"]

    def test_unknown_review_expires(self) -> None:
        """查不到 review_id 必须回执 expired，不能静默忽略（否则卡片永远停在待处理）。"""
        result = review.resolve("no-such-id", ReviewDecision.APPROVE)
        assert result["status"] == ReviewStatus.EXPIRED.value
        assert result["review_id"] == "no-such-id"

    def test_list_pending_filters_by_session_and_state(self, tmp_path: Path) -> None:
        mm = _make_mm(tmp_path)
        first = review.publish(_draft(memory_id="a"), "s1", "t", mm)
        review.publish(_draft(memory_id="b"), "s2", "t", mm)

        assert [r.review_id for r in review.list_pending("s1")] == [first.review_id]

        review.resolve(first.review_id, ReviewDecision.APPROVE)
        assert review.list_pending("s1") == []

    def test_registry_evicts_oldest(self, tmp_path: Path) -> None:
        """超过 MAX_PENDING 时最旧的一条被淘汰，再决定时报 expired。"""
        mm = _make_mm(tmp_path)
        oldest = review.publish(_draft(memory_id="oldest"), "s", "t", mm)
        for i in range(MAX_PENDING):
            review.publish(_draft(memory_id=f"id{i}"), "s", "t", mm)

        result = review.resolve(oldest.review_id, ReviewDecision.APPROVE)
        assert result["status"] == ReviewStatus.EXPIRED.value


# ── 工具接入 ──────────────────────────────────────────────────


class TestCreateMemoryRegistersDraft:
    """create_memory 工具只在写入成功后登记草稿。"""

    def setup_method(self) -> None:
        review.reset()

    def teardown_method(self) -> None:
        consumer.set_current_mm(None)
        review.reset()

    @pytest.mark.parametrize("section", sorted(REVIEW_THEME_KEYS))
    def test_review_theme_create_registers_draft(self, tmp_path: Path, section: str) -> None:
        mm = _make_mm(tmp_path)
        result = consumer.create_memory.invoke(
            {"content": "一条待复核的记忆。", "section": section}
        )

        drafts = review.drain_drafts()
        assert len(drafts) == 1
        # 草稿里的 id 必须与工具返回串中的 id 一致，否则撤销会删错条目
        assert f"[{drafts[0].memory_id}]" in result
        assert drafts[0].memory_id in {i["id"] for i in mm.show()}
        assert drafts[0].theme == section

    @pytest.mark.parametrize(
        "section", sorted(set(THEME_LABELS) - REVIEW_THEME_KEYS)
    )
    def test_other_theme_create_skips_draft(self, tmp_path: Path, section: str) -> None:
        _make_mm(tmp_path)
        result = consumer.create_memory.invoke(
            {"content": "一条普通记忆。", "section": section}
        )
        assert "已创建 [" in result
        assert review.drain_drafts() == []

    def test_oversized_create_skips_draft(self, tmp_path: Path) -> None:
        """超长被驳回时没有写盘，也就没有可撤销的对象。"""
        _make_mm(tmp_path)
        result = consumer.create_memory.invoke(
            {"content": "长" * 80, "section": "TECH"}
        )
        assert "驳回" in result
        assert review.drain_drafts() == []

    def test_invalid_section_skips_draft(self, tmp_path: Path) -> None:
        _make_mm(tmp_path)
        result = consumer.create_memory.invoke(
            {"content": "一条记忆。", "section": "健康"}
        )
        assert "驳回" in result
        assert review.drain_drafts() == []

    def test_reject_cleans_dangling_related(self, tmp_path: Path) -> None:
        """撤销 create 必须清掉其他条目 related 里的悬空引用（delete 是 add 的逆运算）。"""
        mm = _make_mm(tmp_path)
        target = mm.add(description="既有记忆。", theme="USER")

        consumer.create_memory.invoke(
            {
                "content": "关联型技术结论。",
                "section": "TECH",
                "related": [target],
            }
        )
        draft = review.drain_drafts()[0]
        assert draft.memory_id in _load_items(tmp_path)[target]["related"]

        pending = review.publish(draft, "s", "t", mm)
        review.resolve(pending.review_id, ReviewDecision.REJECT)

        items = _load_items(tmp_path)
        assert draft.memory_id not in items
        assert items[target]["related"] == []


# ── 消费者派发 ────────────────────────────────────────────────


class TestConsumerPublishesReviews:
    """MemoryConsumer 在 finally 中发布草稿。"""

    def setup_method(self) -> None:
        review.reset()

    def teardown_method(self) -> None:
        consumer.set_current_mm(None)
        review.reset()

    @pytest.mark.asyncio
    async def test_published_before_done(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        sender_spy: tuple[list[str], MagicMock],
    ) -> None:
        """复核卡片必须在 memory_done 之前推送，前端才能与记忆日志一起渲染。"""
        calls, sender = sender_spy
        mm = _make_mm(tmp_path)
        mid = mm.add(description="技术结论。", theme="TECH")

        agent = _fake_agent(setup=lambda: review.record_create(mid, "技术结论。", "TECH"))
        monkeypatch.setattr(consumer, "create_agent", lambda **kw: agent)
        await consumer.MemoryConsumer(MagicMock()).consume(
            "sess", "turn-1", [{"role": "user", "content": "你好"}]
        )

        assert calls.index("memory_start") < calls.index(f"review:{mid}")
        assert calls.index(f"review:{mid}") < calls.index("memory_done")
        assert sender.memory_review_required.call_count == 1
        assert len(review.list_pending("sess")) == 1

    @pytest.mark.asyncio
    async def test_publishes_even_when_agent_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        sender_spy: tuple[list[str], MagicMock],
    ) -> None:
        """agent 抛异常时工具可能已经写盘，卡片必须照发，否则条目永远得不到复核。"""
        _calls, sender = sender_spy
        mm = _make_mm(tmp_path)
        mid = mm.add(description="技术结论。", theme="TECH")

        agent = _fake_agent(
            setup=lambda: review.record_create(mid, "技术结论。", "TECH"),
            raise_exc=RuntimeError("boom"),
        )
        monkeypatch.setattr(consumer, "create_agent", lambda **kw: agent)
        await consumer.MemoryConsumer(MagicMock()).consume(
            "sess", "turn-1", [{"role": "user", "content": "你好"}]
        )

        assert sender.memory_review_required.call_count == 1
        assert len(review.list_pending("sess")) == 1

    @pytest.mark.asyncio
    async def test_no_session_discards_drafts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        sender_spy: tuple[list[str], MagicMock],
    ) -> None:
        """没有 session_id 时前端无从关联，草稿必须丢弃而不是留在注册表里。"""
        _calls, sender = sender_spy
        mm = _make_mm(tmp_path)
        mid = mm.add(description="技术结论。", theme="TECH")

        agent = _fake_agent(setup=lambda: review.record_create(mid, "技术结论。", "TECH"))
        monkeypatch.setattr(consumer, "create_agent", lambda **kw: agent)
        await consumer.MemoryConsumer(MagicMock()).consume(
            None, "turn-1", [{"role": "user", "content": "你好"}]
        )

        assert sender.memory_review_required.call_count == 0
        assert review.drain_drafts() == []

    @pytest.mark.asyncio
    async def test_empty_turn_id_discards_drafts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        sender_spy: tuple[list[str], MagicMock],
    ) -> None:
        """空 turn_id 前端永远匹配不到轮次，必须丢弃。"""
        _calls, sender = sender_spy
        mm = _make_mm(tmp_path)
        mid = mm.add(description="技术结论。", theme="TECH")

        agent = _fake_agent(setup=lambda: review.record_create(mid, "技术结论。", "TECH"))
        monkeypatch.setattr(consumer, "create_agent", lambda **kw: agent)
        await consumer.MemoryConsumer(MagicMock()).consume(
            "sess", "", [{"role": "user", "content": "你好"}]
        )

        assert sender.memory_review_required.call_count == 0
        assert review.drain_drafts() == []

    @pytest.mark.asyncio
    async def test_stale_draft_from_previous_turn_is_dropped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        sender_spy: tuple[list[str], MagicMock],
    ) -> None:
        """上一轮异常遗留的草稿不能混进本轮推送（防跨轮串号）。"""
        _calls, sender = sender_spy
        _make_mm(tmp_path)
        review.record_create("stale-id", "上一轮遗留。", "TECH")

        monkeypatch.setattr(consumer, "create_agent", lambda **kw: _fake_agent())
        await consumer.MemoryConsumer(MagicMock()).consume(
            "sess", "turn-1", [{"role": "user", "content": "你好"}]
        )

        assert sender.memory_review_required.call_count == 0
        assert review.drain_drafts() == []
