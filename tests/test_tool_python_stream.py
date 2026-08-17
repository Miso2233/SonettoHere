"""测试：run_python 流式推送（tool_stream 事件）。

核心保证：
1. 每执行一次 print 就推送一条 tool_stream，chunk 即该次 print 的输出；
2. tool_stream 的 call_id 与 run_manager.run_id 一致（与 tool_start/end 事件
   共用同一个 run_id，前端可精确匹配气泡，不依赖 tool_name）；
3. 无 run_manager（run_id 为空）时退化为一次性捕获，不推送流、不依赖
   WebSocket 上下文。
"""

import uuid

import pytest

from api.agent import interaction
from tools.system import tool_python as tool_module
from tools.system.tool_python import RunPythonTool


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


@pytest.mark.asyncio
async def test_run_python_streams_each_print(monkeypatch):
    """每次 print 推送一条 tool_stream，且 call_id 与 run_id 一致。"""
    sid = "stream-session"
    run_id = uuid.uuid4()
    interaction.current_session_id.set(sid)
    interaction.set_session_auto_approve(sid, True)

    fake_sender = _FakeSender()
    monkeypatch.setattr(
        tool_module,
        "ToolSender",
        type("TS", (), {"from_context": staticmethod(lambda: fake_sender)}),
    )

    try:
        result = await RunPythonTool()._arun(
            code="print('第一行'); print('第二行')",
            run_manager=_FakeRunManager(run_id),
        )

        # 返回值仍为完整输出（LLM / tool_data 需要）
        assert "第一行" in result
        assert "第二行" in result

        # 输出按增量逐段推送（print 的正文与换行是两次 write，故至少 2 段），
        # 顺序拼接后与一次捕获完全一致
        assert len(fake_sender.streams) >= 2
        joined = "".join(s["chunk"] for s in fake_sender.streams)
        assert joined == "第一行\n第二行\n"

        # 逐条携带与 tool_start/end 一致的 call_id
        assert all(s["call_id"] == str(run_id) for s in fake_sender.streams)
        assert all(s["tool_name"] == "run_python" for s in fake_sender.streams)
    finally:
        interaction.clear_session_settings(sid)
        interaction.current_session_id.set("")


@pytest.mark.asyncio
async def test_run_python_streams_stderr_as_well(monkeypatch):
    """stderr 写入同样被实时推送（如 print(..., file=sys.stderr)）。"""
    sid = "stream-stderr"
    run_id = uuid.uuid4()
    interaction.current_session_id.set(sid)
    interaction.set_session_auto_approve(sid, True)

    fake_sender = _FakeSender()
    monkeypatch.setattr(
        tool_module,
        "ToolSender",
        type("TS", (), {"from_context": staticmethod(lambda: fake_sender)}),
    )

    try:
        result = await RunPythonTool()._arun(
            code="import sys; print('到stderr', file=sys.stderr); print('到stdout')",
            run_manager=_FakeRunManager(run_id),
        )
        assert "到stderr" in result
        assert "到stdout" in result
        joined = "".join(s["chunk"] for s in fake_sender.streams)
        assert "到stderr" in joined
        assert "到stdout" in joined
        assert all(s["call_id"] == str(run_id) for s in fake_sender.streams)
    finally:
        interaction.clear_session_settings(sid)
        interaction.current_session_id.set("")


@pytest.mark.asyncio
async def test_run_python_no_run_manager_falls_back_to_oneshot(monkeypatch):
    """无 run_manager（run_id 为空）时不推送流、不获取 sender，退化为一次性捕获。"""
    sid = "stream-fallback"
    interaction.current_session_id.set(sid)
    interaction.set_session_auto_approve(sid, True)

    class BoomSender:
        @staticmethod
        def from_context():
            raise AssertionError("无 run_id 时不应获取 sender")

    monkeypatch.setattr(tool_module, "ToolSender", BoomSender)

    try:
        result = await RunPythonTool()._arun(code="print('仅一次性捕获')")
        assert "仅一次性捕获" in result
    finally:
        interaction.clear_session_settings(sid)
        interaction.current_session_id.set("")
