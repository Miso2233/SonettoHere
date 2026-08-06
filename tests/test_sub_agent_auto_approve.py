"""测试：子 Agent 会话「自动执行」按钮的上下文传播。

回归背景：子 Agent 会话中点击自动执行按钮变绿后，run_python 仍弹出手动放行。

根因：run_python 的 auto_approve 检查依赖 interaction.current_session_id
这个 ContextVar（tools/system/tool_python.py 读取后查 _settings）。而该
ContextVar 只在 _handle_chat 中设置，子 Agent 任务由 _resume_sub_agent
启动（那里只设置了 current_ws），导致子 Agent 上下文中 current_session_id
为空串，`if session_id and get_session_auto_approve(...)` 恒为 False。

修复：websocket_chat 建立连接时统一设置 current_session_id，使包括
_resume_sub_agent 派生的所有任务继承正确会话 ID。
"""

import asyncio

import pytest
from fastapi import WebSocketDisconnect

from api.agent import interaction
from api.routes import chat as chat_module
from api.routes.chat import websocket_chat
from api.session.manager import session_manager
from tools.system import tool_python as tool_module
from tools.system.tool_python import RunPythonTool


class FakeWs:
    """最小 WebSocket 替身，仅提供 run_agent_turn 需要的 app.state。"""

    def __init__(self) -> None:
        self.app = type(
            "App",
            (),
            {"state": type("State", (), {"tool_manager": None, "ltm": None})()},
        )()
        self.sent: list[dict] = []

    async def accept(self) -> None:
        pass

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)


class DisconnectingWs(FakeWs):
    """accept 后下一次 receive_text 即断开，用于结束 websocket_chat 主循环。"""

    async def receive_text(self) -> str:
        await asyncio.sleep(0)  # 让子 Agent 任务获得一次调度机会
        raise WebSocketDisconnect()


# ── run_python 在子 Agent 上下文中的自动执行 ───────────────────


@pytest.mark.asyncio
async def test_run_python_auto_approves_with_subagent_session(monkeypatch):
    """子 Agent 会话开启自动执行后，run_python 直接执行、不再 ask_user。

    若修复回退（子 Agent 上下文读不到会话 ID），_arun 会走到 ask_user 分支，
    此时 ToolSender.from_context 被调用 → BoomSender 抛错使测试失败。
    """
    sub_sid = "sub-auto-approve"
    interaction.current_session_id.set(sub_sid)
    interaction.set_session_auto_approve(sub_sid, True)

    class BoomSender:
        @staticmethod
        def from_context():
            raise AssertionError("auto_approve 开启时不应请求用户放行")

    monkeypatch.setattr(tool_module, "ToolSender", BoomSender)

    result = await RunPythonTool()._arun(code="print('hi from subagent')")

    assert "hi from subagent" in result  # 直接执行并返回 stdout


@pytest.mark.asyncio
async def test_run_python_asks_without_matching_session(monkeypatch):
    """未开启自动执行（或修复前空 session_id）时，run_python 走手动放行分支。"""
    interaction.current_session_id.set("")  # 修复前的空串场景
    interaction.set_session_auto_approve("sub-other", True)  # 与空串不匹配

    class FakeSender:
        def __init__(self) -> None:
            self.asked = False

        async def ask_user(self, **kwargs):  # type: ignore[no-untyped-def]
            self.asked = True

    fake_sender = FakeSender()
    monkeypatch.setattr(
        tool_module,
        "ToolSender",
        type("TS", (), {"from_context": staticmethod(lambda: fake_sender)}),
    )

    # 捕获 _arun 内部注册的 interaction_id，模拟用户点「取消」
    recorded: dict[str, str] = {}
    real_register = interaction.register

    def patched_register():
        iid, fut = real_register()
        recorded["id"] = iid
        return iid, fut

    monkeypatch.setattr(interaction, "register", patched_register)

    task = asyncio.create_task(RunPythonTool()._arun(code="print('x')"))
    await asyncio.sleep(0)  # 让 _arun 执行到 await future

    assert fake_sender.asked is True  # 走了 ask_user 确认分支
    assert interaction.resolve(recorded["id"], {"action": "reject", "reason": "测试拒绝"}) is True
    result = await asyncio.wait_for(task, timeout=1)

    assert "拒绝" in result  # 用户拒绝的格式化错误返回


# ── websocket_chat 连接建立（修复点回归）─────────────────────


@pytest.mark.asyncio
async def test_websocket_chat_sets_session_context_for_subagent(monkeypatch):
    """回归守卫：websocket_chat 建立连接时必须设置 current_session_id。

    这是修复点。子 Agent 任务由 _resume_sub_agent 通过 create_task 派生，
    复制的是 websocket_chat 调用点的 context —— 若连接建立时未设置
    current_session_id，子 Agent 内读到空串，auto_approve 检查恒失败。

    修复前（未设置）：captured == [""]，测试失败。
    修复后（已设置）：captured == [sub.session_id, True]，测试通过。
    """
    sub = session_manager.create_sub_session(task="子任务")
    ws = DisconnectingWs()

    captured: list[object] = []

    async def fake_run_agent_turn(session, task, **kwargs):  # type: ignore[no-untyped-def]
        captured.append(interaction.current_session_id.get())
        captured.append(interaction.get_session_auto_approve(session.session_id))

    # 隔离依赖，聚焦连接建立时的会话上下文设置
    monkeypatch.setattr(chat_module, "run_agent_turn", fake_run_agent_turn)
    monkeypatch.setattr(chat_module, "get_manager", lambda: None)
    monkeypatch.setattr(chat_module, "build_system_prompt", lambda: "")

    async def fake_estimate(*a, **kw):  # type: ignore[no-untyped-def]
        return {}

    monkeypatch.setattr(chat_module, "estimate_context_usage_from_session", fake_estimate)

    interaction.set_session_auto_approve(sub.session_id, True)

    await websocket_chat(ws, sub.session_id)

    # 子 Agent 任务内读到正确的会话 ID + auto_approve
    assert captured == [sub.session_id, True]
    # 连接关闭后清理会话设置，防止内存泄漏
    assert interaction.get_session_auto_approve(sub.session_id) is False

    session_manager._sessions.pop(sub.session_id, None)
