"""LongTermMemoryInterface 集成测试 — 模拟 CLI 完整流程。

验证: 对话历史 → LLM 摘要生成 → MEMORY.md 写入 的端到端路径。
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from memory.narrative import LongTermMemoryInterface


@pytest.mark.asyncio
async def test_full_pipeline_cold_start_to_update(tmp_path):
    """模拟 CLI 完整多轮对话流程。

    1. 用户发送消息 → Agent 回复 → turn_messages 入队
    2. 后台消费者调用 LLM 生成摘要 → 写入 MEMORY.md
    3. 下一轮读取到更新后的叙述
    """
    path = tmp_path / "MEMORY.md"

    # ── 模拟 ChatOpenAI ──────────────────────────────
    llm = MagicMock()
    call_counter = [0]
    received_prompts = []

    async def fake_ainvoke(messages):
        call_counter[0] += 1
        received_prompts.append(messages)
        resp = MagicMock()
        if call_counter[0] == 1:
            resp.content = "第1轮记忆：用户打了招呼。"
        elif call_counter[0] == 2:
            resp.content = "第1轮记忆：用户打了招呼。\n第2轮补充：用户叫Miso，在北京学习网络安全。"
        else:
            resp.content = f"第{call_counter[0]}轮记忆：已更新。"
        return resp

    llm.ainvoke = AsyncMock(side_effect=fake_ainvoke)

    # ── 初始化管线（对应 CLI.__init__ + run 开头） ──
    ltm = LongTermMemoryInterface(path)
    ltm.start_listening(llm)

    # ── 第一轮对话（对应 CLI 中一次 send_history 调用） ──
    turn1 = [
        {"role": "user", "content": "你好，我想介绍一下自己"},
        {"role": "assistant", "content": "你好！请说，我在听。"},
    ]
    await ltm.send_history(turn1)

    # 给后台消费者一点时间处理（实际场景中无需等待，这里是为了稳定断言顺序）
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

    # ── 停止管线（对应 CLI 中 finally: stop_listening） ──
    await ltm.stop_listening()

    # ── 验证 ─────────────────────────────────────────

    # 1. LLM 被调用了 3 次
    assert llm.ainvoke.call_count == 3

    # 2. MEMORY.md 存在且包含最后一次写入的内容
    assert path.exists()
    final_content = path.read_text(encoding="utf-8")
    assert "第3轮记忆" in final_content

    # 3. 第二轮调用收到了第一轮的记忆（叙事传递链路）
    second_call_msgs = llm.ainvoke.call_args_list[1][0][0]
    second_user_msg = second_call_msgs[1].content
    assert "第1轮记忆" in second_user_msg
    assert "Miso" in second_user_msg

    # 4. 第三轮调用收到了第二轮的记忆（累积效果）
    third_call_msgs = llm.ainvoke.call_args_list[2][0][0]
    third_user_msg = third_call_msgs[1].content
    assert "第2轮补充" in third_user_msg
    assert "网络安全" in third_user_msg

    # 5. 消费者已完全停止
    assert ltm._consumer_task is None
    assert ltm._queue is None


@pytest.mark.asyncio
async def test_pipeline_handles_concurrent_sends(tmp_path):
    """验证多轮消息快速连续入队时不会丢失。"""
    path = tmp_path / "MEMORY.md"

    llm = MagicMock()
    processed = []

    async def fake_ainvoke(messages):
        processed.append(messages)
        return MagicMock(content="记忆。")

    llm.ainvoke = AsyncMock(side_effect=fake_ainvoke)

    ltm = LongTermMemoryInterface(path)
    ltm.start_listening(llm)

    # 快速连续投放 5 轮对话
    for i in range(5):
        await ltm.send_history([
            {"role": "user", "content": f"消息{i}"},
            {"role": "assistant", "content": f"回复{i}"},
        ])

    await ltm.stop_listening()

    assert len(processed) == 5
    assert path.read_text(encoding="utf-8") == "记忆。\n"


@pytest.mark.asyncio
async def test_send_history_is_non_blocking(tmp_path):
    """验证 send_history 不等待消费者完成，瞬时返回。"""
    path = tmp_path / "MEMORY.md"

    llm = MagicMock()

    async def slow_ainvoke(messages):
        await asyncio.sleep(0.1)
        return MagicMock(content="慢慢来。")

    llm.ainvoke = AsyncMock(side_effect=slow_ainvoke)

    ltm = LongTermMemoryInterface(path)
    ltm.start_listening(llm)

    import time
    start = time.monotonic()
    for i in range(3):
        await ltm.send_history([{"role": "user", "content": f"msg{i}"}])
    elapsed = time.monotonic() - start

    # send_history 瞬时返回（远小于 3 × 0.1s）
    assert elapsed < 0.05

    await ltm.stop_listening()
    assert llm.ainvoke.call_count == 3
