"""测试：run_python 中途停止（run_python_interrupt）。

核心保证：
1. 真实子进程执行期间调用 interrupt_run 能彻底终止（proc.kill），
   工具返回带 interrupted + user_message 的结果，部分输出仍可见；
2. 代码执行错误时返回统一错误格式（不泄漏 __RUN_PYTHON_ERROR__ 内部标记）；
3. interrupt_run / _ExecHandle.request_stop 幂等（只 kill 一次、只记首条截止信息）。
"""

import asyncio
import json
import time
import uuid

import pytest

from api.agent import interaction
from tools.system import tool_python as tool_module
from tools.system.tool_python import RunPythonTool, _ExecHandle, interrupt_run


class _FakeSender:
    """记录 tool_stream 事件的假发送器。"""

    def __init__(self) -> None:
        self.streams: list[dict] = []

    async def tool_stream(self, call_id: str, tool_name: str, chunk: str) -> None:
        self.streams.append({"call_id": call_id, "tool_name": tool_name, "chunk": chunk})


class _FakeRunManager:
    """最小 run_manager 替身：仅暴露 run_id。"""

    def __init__(self, run_id: uuid.UUID) -> None:
        self.run_id = run_id


def _patch_sender(monkeypatch, fake_sender: _FakeSender) -> None:
    """把 tool_python.ToolSender 替换为返回 fake_sender 的假类。"""
    monkeypatch.setattr(
        tool_module,
        "ToolSender",
        type("TS", (), {"from_context": staticmethod(lambda: fake_sender)}),
    )


@pytest.mark.asyncio
async def test_interrupt_kills_subprocess_mid_run(monkeypatch):
    """执行 time.sleep(100) 期间中断：子进程被彻底 kill，返回 interrupted 结果。"""
    sid = "interrupt-session"
    run_id = uuid.uuid4()
    interaction.current_session_id.set(sid)
    interaction.set_session_auto_approve(sid, True)

    fake_sender = _FakeSender()
    _patch_sender(monkeypatch, fake_sender)

    try:
        task = asyncio.create_task(
            RunPythonTool()._arun(
                code="import time; print('开始'); time.sleep(100)",
                run_manager=_FakeRunManager(run_id),
            )
        )

        # 轮询直到子进程打印「开始」（确认子进程已真正启动、输出已流式到达）
        deadline = time.monotonic() + 10
        while not any("开始" in s["chunk"] for s in fake_sender.streams):
            if task.done() or time.monotonic() > deadline:
                break
            await asyncio.sleep(0.05)

        # 触发中断：同步函数，在同一事件循环线程内 kill 子进程
        assert interrupt_run(str(run_id), "停下来") is True

        result = await asyncio.wait_for(task, timeout=15)
        data = json.loads(result)["data"]
        assert data["interrupted"] is True
        assert data["user_message"] == "停下来"
        assert "开始" in data["output"]

        # 注册表已清理，无残留句柄
        assert str(run_id) not in tool_module._exec_runs
    finally:
        interaction.clear_session_settings(sid)
        interaction.current_session_id.set("")


@pytest.mark.asyncio
async def test_interrupt_unknown_id_returns_false():
    """未知 run_id 的 interrupt_run 返回 False（不抛异常）。"""
    assert interrupt_run("unknown-id", "x") is False


@pytest.mark.asyncio
async def test_code_error_returns_formatted_error(monkeypatch):
    """代码抛出异常：返回统一错误格式，含错误消息，不泄漏内部标记。"""
    sid = "interrupt-error"
    run_id = uuid.uuid4()
    interaction.current_session_id.set(sid)
    interaction.set_session_auto_approve(sid, True)

    fake_sender = _FakeSender()
    _patch_sender(monkeypatch, fake_sender)

    try:
        result = await RunPythonTool()._arun(
            code="raise ValueError('boom')",
            run_manager=_FakeRunManager(run_id),
        )
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert "boom" in parsed["error"]
        assert "__RUN_PYTHON_ERROR__" not in result
    finally:
        interaction.clear_session_settings(sid)
        interaction.current_session_id.set("")


def test_request_stop_is_idempotent():
    """request_stop 幂等：重复调用只 kill 一次、只记录第一条截止信息。"""

    class _FakeProc:
        def __init__(self) -> None:
            self.returncode: int | None = None
            self.kill_count = 0

        def kill(self) -> None:
            self.kill_count += 1
            self.returncode = 1

    fake = _FakeProc()
    handle = _ExecHandle()
    handle.proc = fake  # type: ignore[assignment]

    handle.request_stop("第一次")
    handle.request_stop("第二次")

    assert handle.interrupted is True
    assert handle.user_message == "第一次"
    assert fake.kill_count == 1


def test_interrupt_run_idempotent():
    """interrupt_run 对已中断的 handle 再次调用不重复 kill、不改写消息。"""

    class _FakeProc:
        def __init__(self) -> None:
            self.returncode: int | None = None
            self.kill_count = 0

        def kill(self) -> None:
            self.kill_count += 1
            self.returncode = 1

    fake = _FakeProc()
    run_id = uuid.uuid4()
    handle = _ExecHandle()
    handle.proc = fake  # type: ignore[assignment]
    tool_module._exec_runs[str(run_id)] = handle

    try:
        assert interrupt_run(str(run_id), "A") is True
        assert interrupt_run(str(run_id), "B") is True
        assert handle.interrupted is True
        assert handle.user_message == "A"
        assert fake.kill_count == 1
    finally:
        tool_module._exec_runs.pop(str(run_id), None)
