"""测试 await_background 工具（tools/task/tool_await.py）。

覆盖已完成取回原始结果、超时返回 running、未知索引、列表模式、
空注册表与等待期间取消。
"""

import asyncio
import json
import time

import pytest

from api.agent import background as bg
from api.agent import interaction
from tools.task.tool_await import AwaitBackgroundTool


def _setup_session() -> str:
    sid = f"await-test-{time.time_ns()}"
    interaction.current_session_id.set(sid)
    return sid


def _spawn_slow(registry: bg.BackgroundTaskRegistry, delay: float, value: str) -> int:
    """在注册表中 spawn 一个延迟返回的协程，返回索引。"""

    async def slow() -> str:
        await asyncio.sleep(delay)
        return value

    return registry.register(slow(), tool_name="probe", args_summary="{}").index


def _spawn_never(registry: bg.BackgroundTaskRegistry) -> int:
    """spawn 一个长睡眠协程（不会在测试内完成），返回索引。"""
    return _spawn_slow(registry, 30, "never")


@pytest.mark.asyncio
async def test_completed_returns_raw_result() -> None:
    """已完成任务：原样返回存储的真实工具输出（不套第二层信封）。"""
    sid = _setup_session()
    try:
        registry = bg.get_registry(sid)
        index = _spawn_slow(registry, 0, json.dumps({"success": True, "data": {"n": 1}}))
        await registry.await_result(index, 5)

        result = await AwaitBackgroundTool().arun({"index": index})
        assert json.loads(result)["data"] == {"n": 1}
    finally:
        bg.cancel_session(sid)
        interaction.current_session_id.set("")


@pytest.mark.asyncio
async def test_running_timeout_returns_running_status() -> None:
    """超时仍未完成：返回 running 状态（不阻塞、不报错），任务继续运行。"""
    sid = _setup_session()
    try:
        registry = bg.get_registry(sid)
        index = _spawn_never(registry)

        result = await AwaitBackgroundTool()._arun(index=index, timeout_seconds=0.2)
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["data"]["status"] == "running"
        assert parsed["data"]["task_index"] == index

        # 清理长睡眠任务
        bg.cancel_session(sid)
        assert registry.get(index) is None
    finally:
        interaction.current_session_id.set("")


@pytest.mark.asyncio
async def test_unknown_index_returns_error() -> None:
    """索引不存在：返回统一错误（含排查提示）。"""
    sid = _setup_session()
    try:
        registry = bg.get_registry(sid)
        _spawn_slow(registry, 0, "done")  # 注册表非空，使命中「索引不存在」分支

        result = await AwaitBackgroundTool().arun({"index": 999})
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "不存在" in parsed["error"]
    finally:
        bg.cancel_session(sid)
        interaction.current_session_id.set("")


@pytest.mark.asyncio
async def test_no_tasks_returns_error() -> None:
    """无会话注册表（本进程从未 spawn 过）：返回「没有后台任务」。"""
    interaction.current_session_id.set("")
    result = await AwaitBackgroundTool().arun({"index": 1})
    assert json.loads(result)["success"] is False


@pytest.mark.asyncio
async def test_list_mode() -> None:
    """index=0 列出全部任务：索引、工具名、状态、耗时。"""
    sid = _setup_session()
    try:
        registry = bg.get_registry(sid)
        first = _spawn_slow(registry, 0, "done-1")
        _spawn_never(registry)
        await registry.await_result(first, 5)  # 确保 completed 已回写

        result = await AwaitBackgroundTool().arun({"index": 0})
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["data"]["count"] == 2
        statuses = {t["status"] for t in parsed["data"]["tasks"]}
        assert statuses == {"completed", "running"}
        assert parsed["data"]["tasks"][0]["tool_name"] == "probe"
    finally:
        bg.cancel_session(sid)
        interaction.current_session_id.set("")


@pytest.mark.asyncio
async def test_cancelled_while_waiting() -> None:
    """等待期间任务被取消（turn 取消）：返回统一取消错误。"""
    sid = _setup_session()
    try:
        registry = bg.get_registry(sid)
        index = _spawn_never(registry)

        tool = AwaitBackgroundTool()
        task = asyncio.create_task(tool.arun({"index": index, "timeout_seconds": 5}))
        await asyncio.sleep(0.05)  # 进入 wait_for
        task.cancel()

        result = await asyncio.wait_for(task, timeout=1)
        assert "用户取消了回复" in result
    finally:
        bg.cancel_session(sid)
        interaction.current_session_id.set("")


@pytest.mark.asyncio
async def test_failed_task_returns_error_envelope() -> None:
    """失败任务：await 返回存储的 format_error（由回调路由为 tool_error）。"""
    sid = _setup_session()
    try:
        registry = bg.get_registry(sid)

        async def boom() -> str:
            raise RuntimeError("inner boom")

        index = registry.register(boom(), tool_name="boom", args_summary="{}").index
        await registry.await_result(index, 5)

        result = await AwaitBackgroundTool().arun({"index": index})
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "inner boom" in parsed["error"]
    finally:
        bg.cancel_session(sid)
        interaction.current_session_id.set("")
