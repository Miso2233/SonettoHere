"""测试 call_sub_agent 接入 @background（tools/sub_agent/tool_call_sub_agent.py）。

覆盖后台 spawn / 子轮 resolve 取回、后台等待超时干净失败、
CancelledError re-raise（父会话删除级联）、detached 事件标记，
以及同步模式行为回归（裸等待 + 软取消）。
"""

import asyncio
import json
from types import SimpleNamespace
from typing import Any

import pytest

# api.session.manager 在全新解释器中作为首导入会触发 manager→memory→manager
# 循环（api.memory.long_term 反向依赖 SessionState）；先导入 long_term 打破
# 循环，之后工具内 _do_run 的延迟导入才能正常完成
import api.memory.long_term  # noqa: F401, PLC0415

from api.agent import background as bg
from api.agent import interaction
from tools.sub_agent import tool_call_sub_agent as tool_module
from tools.sub_agent.tool_call_sub_agent import CallSubAgentTool


def _get_session_manager() -> Any:
    # api.session.manager 作为解释器首导入会触发 manager→memory→manager
    # 循环导入（api.memory.long_term 反向依赖 SessionState），先导入
    # long_term 打破循环（与 api.routes.chat 首导入等价）
    import api.memory.long_term  # noqa: F401, PLC0415
    from api.session.manager import session_manager  # noqa: PLC0415

    return session_manager


class FakeWS:
    """最小 WebSocket 替身：_do_run 仅访问 app.state 与 url/path。"""

    def __init__(self) -> None:
        self.app = SimpleNamespace(state=object())

    async def send_json(self, frame: dict[str, Any]) -> None:  # background_update 走真实 ToolSender
        return None
        self.url = "ws://localhost/ws/chat/parent-123"


class FakeSender:
    """记录 sub_session_created 调用参数的最小发送器替身。"""

    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []

    @classmethod
    def from_context(cls) -> "FakeSender":
        return _CURRENT_FAKE[-1]

    async def sub_session_created(self, **kwargs: Any) -> None:
        self.created.append(kwargs)


_CURRENT_FAKE: list[FakeSender] = []


def _patch_sender(monkeypatch: pytest.MonkeyPatch) -> FakeSender:
    fake = FakeSender()
    _CURRENT_FAKE.append(fake)
    monkeypatch.setattr(tool_call_sub_agent, "ToolSender", FakeSender)
    return fake


def _setup(monkeypatch: pytest.MonkeyPatch) -> str:
    sid = f"subbg-{id(monkeypatch)}-{asyncio.get_running_loop().time()}"
    interaction.current_session_id.set(sid)
    interaction.current_ws.set(FakeWS())
    # 替换工具模块命名空间的 ToolSender：sub_session_created 经 FakeSender
    # 捕获（background_update 终态推送走真实 ToolSender → FakeWS.send_json 静默）
    _CURRENT_FAKE.append(FakeSender())
    monkeypatch.setattr(tool_module, "ToolSender", FakeSender)
    return sid


def _teardown() -> None:
    interaction.current_session_id.set("")
    interaction.current_ws.set(None)
    if _CURRENT_FAKE:
        _CURRENT_FAKE.pop()


# ── 后台 spawn 与取回 ───────────────────────────────────────


@pytest.mark.asyncio
async def test_background_spawn_and_resolve(monkeypatch: pytest.MonkeyPatch) -> None:
    """background=True 立即返回索引；子轮 resolve 后 await 取回真实 answer。"""
    sid = _setup(monkeypatch)
    try:
        out = await CallSubAgentTool().arun({"task": "分析代码", "background": True})
        parsed = json.loads(out)
        assert parsed["data"]["background"] is True
        index = parsed["data"]["task_index"]

        # detached 标记已随事件下发
        assert _CURRENT_FAKE[-1].created[0]["detached"] is True

        # 模拟子轮完成：resolve 子会话的 pending future
        sub_id = _CURRENT_FAKE[-1].created[0]["sub_session_id"]
        sub = _get_session_manager().get(sub_id)
        assert sub is not None
        sub.resolve_pending("子 Agent 的回答")

        registry = bg.get_registry(sid)
        bt = await registry.await_result(index, 5)
        assert bt is not None and bt.status == "completed"

        from tools.task.tool_await import AwaitBackgroundTool

        result = await AwaitBackgroundTool().arun({"index": index})
        answer = json.loads(result)
        assert answer["success"] is True
        assert answer["data"]["answer"] == "子 Agent 的回答"
    finally:
        for kw in _CURRENT_FAKE[-1].created:
            _get_session_manager().delete(kw["sub_session_id"])
        bg.cancel_session(sid)
        _teardown()


@pytest.mark.asyncio
async def test_background_wait_timeout_fails_cleanly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """后台等待超时（子会话未被前端启动）：终止子轮、返回明确错误。"""
    sid = _setup(monkeypatch)
    monkeypatch.setattr(tool_module, "_SUB_WAIT_TIMEOUT_S", 0.05)
    try:
        tool = CallSubAgentTool()
        out = await tool.arun({"task": "x", "background": True})
        index = json.loads(out)["data"]["task_index"]

        registry = bg.get_registry(sid)
        bt = await registry.await_result(index, 5)
        assert bt is not None and bt.status == "completed"  # 工具正常返回错误信封
        assert "未被启动" in bt.result

        # 子会话 future 已被标记失败，子轮任务已取消
        assert _CURRENT_FAKE[-1].created[0]["detached"] is True
    finally:
        for kw in _CURRENT_FAKE[-1].created:
            _get_session_manager().delete(kw["sub_session_id"])
        bg.cancel_session(sid)
        _teardown()


@pytest.mark.asyncio
async def test_background_cancelled_reraises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """detached 任务被取消（父会话删除级联）：re-raise → 注册表记 failed。"""
    sid = _setup(monkeypatch)
    try:
        out = await CallSubAgentTool().arun({"task": "x", "background": True})
        index = json.loads(out)["data"]["task_index"]

        registry = bg.get_registry(sid)
        bt = registry.get(index)
        assert bt is not None and bt.task is not None
        await asyncio.sleep(0.05)  # 进入等待
        bt.task.cancel()

        await asyncio.wait_for(asyncio.shield(bt.future), 5)
        assert bt.status == "failed"
        assert "已被取消" in bt.result
    finally:
        for kw in _CURRENT_FAKE[-1].created:
            _get_session_manager().delete(kw["sub_session_id"])
        bg.cancel_session(sid)
        _teardown()


# ── 同步模式回归 ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sync_mode_resolves_and_reports_not_detached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同步模式：等待 resolve 返回结果，事件 detached 为 False。"""
    sid = _setup(monkeypatch)
    try:
        task = asyncio.create_task(CallSubAgentTool().arun({"task": "x"}))
        await asyncio.sleep(0.1)  # 进入裸 await

        created = _CURRENT_FAKE[-1].created[0]
        assert created["detached"] is False

        sub = _get_session_manager().get(created["sub_session_id"])
        assert sub is not None
        sub.resolve_pending("同步回答")

        result = await asyncio.wait_for(task, 5)
        parsed = json.loads(result)
        assert parsed["data"]["answer"] == "同步回答"
    finally:
        for kw in _CURRENT_FAKE[-1].created:
            _get_session_manager().delete(kw["sub_session_id"])
        _teardown()


@pytest.mark.asyncio
async def test_sync_mode_cancel_propagates_and_cleans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同步模式软取消：父任务取消 → 子 Agent 终止、返回取消错误（行为不变）。"""
    sid = _setup(monkeypatch)
    try:
        task = asyncio.create_task(CallSubAgentTool().arun({"task": "x"}))
        await asyncio.sleep(0.1)  # 进入裸 await

        task.cancel()
        result = await asyncio.wait_for(task, 5)
        assert "主任务被取消" in result

        # 子会话 future 已被取消
        sub = _get_session_manager().get(_CURRENT_FAKE[-1].created[0]["sub_session_id"])
        assert sub is not None and sub.pending_future.done()
    finally:
        for kw in _CURRENT_FAKE[-1].created:
            _get_session_manager().delete(kw["sub_session_id"])
        _teardown()
