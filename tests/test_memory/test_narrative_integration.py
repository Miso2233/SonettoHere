"""LongTermMemory + MemoryConsumer 集成测试 — 模拟 CLI 完整流程。

验证: 对话历史 → CRUD Agent → memory.yaml 写入 的端到端路径。
"""

import asyncio
from typing import Any, Callable
from unittest.mock import AsyncMock, MagicMock

import pytest

import api.memory.consumer as consumer
from api.memory.long_term import LongTermMemory
from api.memory.manager import MemoryManagerBuilder, YamlMemoryManager


def _make_fake_agent(
    entries_setup: Callable[[], None] | None = None,
    done_event: asyncio.Event | None = None,
):
    """构建 mock agent，ainvoke 时执行 entries_setup 修改当前 MemoryManager。

    done_event 若提供，则在 ainvoke 完成时 set，供测试事件驱动地等待消费完成。
    """

    async def fake_ainvoke(_input: object, config: dict[str, Any] | None = None) -> dict[str, Any]:
        if entries_setup:
            entries_setup()
        if done_event is not None:
            done_event.set()
        return {"messages": []}

    agent = MagicMock()
    agent.ainvoke = AsyncMock(side_effect=fake_ainvoke)
    return agent


async def _wait_for_event(event: asyncio.Event, timeout: float = 5.0) -> None:
    """等待事件置位，超时抛出断言错误（替代固定 sleep 的确定化等待）。"""
    try:
        await asyncio.wait_for(event.wait(), timeout=timeout)
    except asyncio.TimeoutError as e:
        raise AssertionError(f"等待事件超时（{timeout}s），消费者未按预期处理消息") from e


@pytest.mark.asyncio
async def test_full_pipeline_cold_start_to_update(tmp_path, monkeypatch):
    """模拟 CLI 完整多轮对话流程。

    1. 用户发送消息 → turn_messages 入队
    2. 后台 Agent 调用 CRUD 工具 → 修改 MemoryManager
    3. _consumer 写入 memory.yaml
    4. 下一轮读取到更新后的记忆
    """
    path = tmp_path / "memory.yaml"

    call_count = [0]
    captured_prompts = []
    # 每轮完成事件预创建，避免等待时尚未创建导致 IndexError
    turn_done: list[asyncio.Event] = [asyncio.Event() for _ in range(3)]

    def agent_factory(**kwargs):
        call_count[0] += 1
        captured_prompts.append(kwargs.get("system_prompt", ""))
        done = turn_done[call_count[0] - 1]

        if call_count[0] == 1:

            def setup1():
                consumer._current_mm.add(
                    description="第1轮记忆：用户打了招呼。", theme="身份"
                )

            return _make_fake_agent(entries_setup=setup1, done_event=done)
        elif call_count[0] == 2:

            def setup2():
                mm = consumer._current_mm
                mm.add(description="第1轮记忆：用户打了招呼。", theme="身份")
                mm.add(
                    description="第2轮补充：用户叫Miso，在北京学习网络安全。",
                    theme="身份",
                )

            return _make_fake_agent(entries_setup=setup2, done_event=done)
        else:

            def setup3():
                mm = consumer._current_mm
                for item in mm.show():
                    mm.delete(item["id"])
                mm.add(description=f"第{call_count[0]}轮记忆：已更新。", theme="身份")

            return _make_fake_agent(entries_setup=setup3, done_event=done)

    monkeypatch.setattr(consumer, "create_agent", agent_factory)
    monkeypatch.setattr("api.memory.long_term.get_manager", lambda: MagicMock(get_default_llm=lambda: MagicMock()))

    # ── 初始化管线 ──
    ltm = LongTermMemory(MemoryManagerBuilder().with_backend(YamlMemoryManager).with_args(yaml_file=str(path)).build())
    ltm.start()

    # ── 第一轮对话 ──
    turn1 = [
        {"role": "user", "content": "你好，我想介绍一下自己"},
        {"role": "assistant", "content": "你好！请说，我在听。"},
    ]
    await ltm.send_history(turn1)
    await _wait_for_event(turn_done[0])

    # ── 第二轮对话 ──
    turn2 = [
        {"role": "user", "content": "我叫Miso，在学网络安全"},
        {"role": "tool", "content": "查询结果：无"},
        {"role": "assistant", "content": "好的Miso，我记住了！"},
    ]
    await ltm.send_history(turn2)
    await _wait_for_event(turn_done[1])

    # ── 第三轮对话 ──
    turn3 = [
        {"role": "user", "content": "帮我查一下今天的CVE"},
        {"role": "assistant", "content": "今天暂无新CVE。"},
    ]
    await ltm.send_history(turn3)

    # ── 停止管线 ──
    await ltm.stop()

    # ── 验证 ──

    # 1. Agent 被创建了 3 次
    assert call_count[0] == 3

    # 2. memory.yaml 存在且包含最后一次写入的内容
    assert path.exists()
    final_content = path.read_text(encoding="utf-8")
    assert "第3轮记忆" in final_content

    # 3. 第二轮用了 UPDATE_SYSTEM（已有 memory.yaml）
    assert "记忆叙事师" in captured_prompts[1]

    # 4. 消费者已完全停止
    assert ltm._consumer_task is None
    assert ltm._queue is None


@pytest.mark.asyncio
async def test_pipeline_handles_concurrent_sends(tmp_path, monkeypatch):
    """验证多轮消息快速连续入队时不会丢失。"""
    path = tmp_path / "memory.yaml"

    processed_count = [0]

    def agent_factory(**kwargs):
        def setup():
            processed_count[0] += 1
            consumer._current_mm.add(
                description=f"记忆{processed_count[0]}。",
                theme="身份",
            )

        return _make_fake_agent(entries_setup=setup)

    monkeypatch.setattr(consumer, "create_agent", agent_factory)
    monkeypatch.setattr("api.memory.long_term.get_manager", lambda: MagicMock(get_default_llm=lambda: MagicMock()))

    ltm = LongTermMemory(MemoryManagerBuilder().with_backend(YamlMemoryManager).with_args(yaml_file=str(path)).build())
    ltm.start()

    # 快速连续投放 5 轮对话
    for i in range(5):
        await ltm.send_history(
            [
                {"role": "user", "content": f"消息{i}"},
                {"role": "assistant", "content": f"回复{i}"},
            ]
        )

    await ltm.stop()

    assert processed_count[0] == 5
    content = path.read_text(encoding="utf-8")
    for i in range(1, 6):
        assert f"记忆{i}" in content


@pytest.mark.asyncio
async def test_send_history_is_non_blocking(tmp_path, monkeypatch):
    """验证 send_history 不等待消费者完成，瞬时返回。"""
    path = tmp_path / "memory.yaml"

    async def slow_ainvoke(_input: object, config: dict[str, Any] | None = None) -> dict[str, Any]:
        await asyncio.sleep(0.1)
        consumer._current_mm.add(description="慢慢来。", theme="身份")
        return {"messages": []}

    fake_agent = MagicMock()
    fake_agent.ainvoke = AsyncMock(side_effect=slow_ainvoke)
    monkeypatch.setattr(consumer, "create_agent", lambda **kw: fake_agent)
    monkeypatch.setattr("api.memory.long_term.get_manager", lambda: MagicMock(get_default_llm=lambda: MagicMock()))

    ltm = LongTermMemory(MemoryManagerBuilder().with_backend(YamlMemoryManager).with_args(yaml_file=str(path)).build())
    ltm.start()

    import time

    start = time.monotonic()
    for i in range(3):
        await ltm.send_history([{"role": "user", "content": f"msg{i}"}])
    elapsed = time.monotonic() - start

    # send_history 瞬时返回（远小于 3 × 0.1s）
    assert elapsed < 0.05

    await ltm.stop()
    assert fake_agent.ainvoke.call_count == 3
