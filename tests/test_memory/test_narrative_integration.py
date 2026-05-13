"""LongTermMemoryInterface 集成测试 — 模拟 CLI 完整流程。

验证: 对话历史 → CRUD Agent → MEMORY.md 写入 的端到端路径。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

import memory.narrative as narrative
from memory.narrative import LongTermMemoryInterface


def _make_fake_agent(entries_setup=None):
    """构建 mock agent，ainvoke 时执行 entries_setup 修改 _current_entries。"""
    async def fake_ainvoke(_input, config=None):
        if entries_setup:
            entries_setup()
        return {"messages": []}

    agent = MagicMock()
    agent.ainvoke = AsyncMock(side_effect=fake_ainvoke)
    return agent


@pytest.mark.asyncio
async def test_full_pipeline_cold_start_to_update(tmp_path, monkeypatch):
    """模拟 CLI 完整多轮对话流程。

    1. 用户发送消息 → turn_messages 入队
    2. 后台 Agent 调用 CRUD 工具 → 修改 _current_entries
    3. _consumer 序列化并写入 MEMORY.md
    4. 下一轮读取到更新后的记忆
    """
    path = tmp_path / "MEMORY.md"

    call_count = [0]
    captured_prompts = []

    def agent_factory(**kwargs):
        call_count[0] += 1
        captured_prompts.append(kwargs.get("prompt", ""))

        if call_count[0] == 1:
            def setup1():
                narrative.MemoryStore().entries["1"] = "第1轮记忆：用户打了招呼。"
            return _make_fake_agent(entries_setup=setup1)
        elif call_count[0] == 2:
            def setup2():
                narrative.MemoryStore().entries["1"] = "第1轮记忆：用户打了招呼。"
                narrative.MemoryStore().entries["2"] = "第2轮补充：用户叫Miso，在北京学习网络安全。"
            return _make_fake_agent(entries_setup=setup2)
        else:
            def setup3():
                narrative.MemoryStore().entries["1"] = f"第{call_count[0]}轮记忆：已更新。"
            return _make_fake_agent(entries_setup=setup3)

    monkeypatch.setattr(narrative, "create_react_agent", agent_factory)

    # ── 初始化管线 ──
    ltm = LongTermMemoryInterface(path)
    ltm.start_listening(MagicMock())

    # ── 第一轮对话 ──
    turn1 = [
        {"role": "user", "content": "你好，我想介绍一下自己"},
        {"role": "assistant", "content": "你好！请说，我在听。"},
    ]
    await ltm.send_history(turn1)
    await asyncio.sleep(0.05)

    # ── 第二轮对话 ──
    turn2 = [
        {"role": "user", "content": "我叫Miso，在学网络安全"},
        {"role": "tool", "content": "查询结果：无"},
        {"role": "assistant", "content": "好的Miso，我记住了！"},
    ]
    await ltm.send_history(turn2)
    await asyncio.sleep(0.05)

    # ── 第三轮对话 ──
    turn3 = [
        {"role": "user", "content": "帮我查一下今天的CVE"},
        {"role": "assistant", "content": "今天暂无新CVE。"},
    ]
    await ltm.send_history(turn3)

    # ── 停止管线 ──
    await ltm.stop_listening()

    # ── 验证 ──

    # 1. Agent 被创建了 3 次
    assert call_count[0] == 3

    # 2. MEMORY.md 存在且包含最后一次写入的内容
    assert path.exists()
    final_content = path.read_text(encoding="utf-8")
    assert "第3轮记忆" in final_content

    # 3. 第二轮用了 UPDATE_SYSTEM（已有 MEMORY.md）
    assert "记忆叙事师" in captured_prompts[1]

    # 4. 消费者已完全停止
    assert ltm._consumer_task is None
    assert ltm._queue is None


@pytest.mark.asyncio
async def test_pipeline_handles_concurrent_sends(tmp_path, monkeypatch):
    """验证多轮消息快速连续入队时不会丢失。"""
    path = tmp_path / "MEMORY.md"

    processed_count = [0]

    def agent_factory(**kwargs):
        def setup():
            processed_count[0] += 1
            narrative.MemoryStore().entries[str(processed_count[0])] = f"记忆{processed_count[0]}。"
        return _make_fake_agent(entries_setup=setup)

    monkeypatch.setattr(narrative, "create_react_agent", agent_factory)

    ltm = LongTermMemoryInterface(path)
    ltm.start_listening(MagicMock())

    # 快速连续投放 5 轮对话
    for i in range(5):
        await ltm.send_history([
            {"role": "user", "content": f"消息{i}"},
            {"role": "assistant", "content": f"回复{i}"},
        ])

    await ltm.stop_listening()

    assert processed_count[0] == 5
    content = path.read_text(encoding="utf-8")
    for i in range(1, 6):
        assert f"记忆{i}" in content


@pytest.mark.asyncio
async def test_send_history_is_non_blocking(tmp_path, monkeypatch):
    """验证 send_history 不等待消费者完成，瞬时返回。"""
    path = tmp_path / "MEMORY.md"

    async def slow_ainvoke(_input, config=None):
        await asyncio.sleep(0.1)
        narrative.MemoryStore().entries["1"] = "慢慢来。"
        return {"messages": []}

    fake_agent = MagicMock()
    fake_agent.ainvoke = AsyncMock(side_effect=slow_ainvoke)
    monkeypatch.setattr(narrative, "create_react_agent", lambda **kw: fake_agent)

    ltm = LongTermMemoryInterface(path)
    ltm.start_listening(MagicMock())

    import time
    start = time.monotonic()
    for i in range(3):
        await ltm.send_history([{"role": "user", "content": f"msg{i}"}])
    elapsed = time.monotonic() - start

    # send_history 瞬时返回（远小于 3 × 0.1s）
    assert elapsed < 0.05

    await ltm.stop_listening()
    assert fake_agent.ainvoke.call_count == 3
