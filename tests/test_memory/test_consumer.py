"""api.memory.consumer 测试 —— 单轮记忆处理的收尾保证。

收尾事件（``memory_done``）是前端「处理中」图标的唯一解药：只要它没发出去，
该轮就会永久停在处理中。因此 agent 报错、agent 挂死（看门狗）、复核发布失败
这三条路径都必须照常收尾。
"""

import asyncio
from pathlib import Path
from typing import Any, Callable
from unittest.mock import AsyncMock, MagicMock

import pytest

import api.memory.consumer as consumer
import api.memory.review as review
from api.memory.manager import YamlMemoryManager


# ── 测试辅助 ──────────────────────────────────────────────────


def _make_mm(tmp_path: Path) -> YamlMemoryManager:
    """创建 YAML 记忆管理器并注册为当前管理器。"""
    mm = YamlMemoryManager(yaml_file=str(tmp_path / "memory.yaml"))
    consumer.set_current_mm(mm)
    return mm


def _agent(setup: Callable[[], None] | None = None, exc: Exception | None = None) -> MagicMock:
    """假 CRUD agent：可选先登记草稿，再抛异常。"""
    async def _ainvoke(*_a: Any, **_k: Any) -> None:
        if setup is not None:
            setup()
        if exc is not None:
            raise exc

    agent = MagicMock()
    agent.ainvoke = AsyncMock(side_effect=_ainvoke)
    return agent


def _hanging_agent(setup: Callable[[], None] | None = None) -> MagicMock:
    """假 agent：ainvoke 永不返回，模拟上游 LLM 挂死。"""
    async def _ainvoke(*_a: Any, **_k: Any) -> None:
        if setup is not None:
            setup()
        await asyncio.sleep(30)

    agent = MagicMock()
    agent.ainvoke = AsyncMock(side_effect=_ainvoke)
    return agent


@pytest.fixture
def sender_spy(monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], MagicMock]:
    """打桩 MemorySender：记录事件到达顺序，用于断言「收尾是否发生」。"""
    calls: list[str] = []
    sender = MagicMock()
    sender.memory_start = AsyncMock(side_effect=lambda *a, **k: calls.append("memory_start"))
    sender.memory_done = AsyncMock(side_effect=lambda *a, **k: calls.append("memory_done"))
    sender.memory_review_required = AsyncMock(
        side_effect=lambda payload: calls.append(f"review:{payload['memory_id']}")
    )
    monkeypatch.setattr(
        consumer.MemorySender, "from_session_id", staticmethod(lambda _sid: sender)
    )
    return calls, sender


class TestConsumerAlwaysFinishes:
    """无论 agent 怎么结束，memory_done 都必须发出。"""

    def setup_method(self) -> None:
        review.reset()

    def teardown_method(self) -> None:
        consumer.set_current_mm(None)
        review.reset()

    @pytest.mark.asyncio
    async def test_hanging_agent_times_out_and_still_finishes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        sender_spy: tuple[list[str], MagicMock],
    ) -> None:
        """agent 挂死时看门狗必须介入：已登记的复核照发，且收尾事件不缺席。"""
        calls, sender = sender_spy
        mm = _make_mm(tmp_path)
        mid = mm.add(description="技术结论。", theme="TECH")

        monkeypatch.setattr(consumer, "CONSUMER_TIMEOUT_S", 0.05)
        monkeypatch.setattr(
            consumer, "create_agent",
            lambda **_kw: _hanging_agent(
                setup=lambda: review.record_create(mid, "技术结论。", "TECH")
            ),
        )
        await consumer.MemoryConsumer(MagicMock()).consume(
            "sess", "turn-1", [{"role": "user", "content": "你好"}]
        )

        assert calls == ["memory_start", f"review:{mid}", "memory_done"]
        assert len(review.list_pending("sess")) == 1

    @pytest.mark.asyncio
    async def test_publish_step_raising_does_not_skip_done(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        sender_spy: tuple[list[str], MagicMock],
    ) -> None:
        """发布环节整体抛异常时 memory_done 仍须发出（收尾兜底）。"""
        calls, _sender = sender_spy
        _make_mm(tmp_path)

        async def _boom(*_a: Any, **_k: Any) -> int:
            raise RuntimeError("草稿登记区炸了")

        monkeypatch.setattr(consumer.MemoryConsumer, "_publish_reviews", staticmethod(_boom))
        monkeypatch.setattr(
            consumer, "create_agent", lambda **_kw: _agent()
        )
        await consumer.MemoryConsumer(MagicMock()).consume(
            "sess", "turn-1", [{"role": "user", "content": "你好"}]
        )

        assert "memory_done" in calls

    @pytest.mark.asyncio
    async def test_single_card_push_failure_does_not_skip_done(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        sender_spy: tuple[list[str], MagicMock],
    ) -> None:
        """单张卡片推送失败由 _publish_reviews 内部消化，同样不得吃掉收尾事件。"""
        calls, _sender = sender_spy
        mm = _make_mm(tmp_path)
        mid = mm.add(description="技术结论。", theme="TECH")

        def _boom(*_a: Any, **_k: Any) -> None:
            raise RuntimeError("注册表写炸了")

        monkeypatch.setattr(review, "publish", _boom)
        monkeypatch.setattr(
            consumer, "create_agent",
            lambda **_kw: _agent(setup=lambda: review.record_create(mid, "技术结论。", "TECH")),
        )
        await consumer.MemoryConsumer(MagicMock()).consume(
            "sess", "turn-1", [{"role": "user", "content": "你好"}]
        )

        assert "memory_done" in calls

    @pytest.mark.asyncio
    async def test_agent_error_still_finishes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        sender_spy: tuple[list[str], MagicMock],
    ) -> None:
        """agent 报错是最常见的路径，收尾照旧（原有行为的回归保护）。"""
        calls, _sender = sender_spy
        _make_mm(tmp_path)

        monkeypatch.setattr(
            consumer, "create_agent",
            lambda **_kw: _agent(exc=RuntimeError("provider 500")),
        )
        await consumer.MemoryConsumer(MagicMock()).consume(
            "sess", "turn-1", [{"role": "user", "content": "你好"}]
        )

        assert calls == ["memory_start", "memory_done"]
