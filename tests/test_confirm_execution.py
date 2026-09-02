"""测试 confirm_execution 装饰器（tools/confirm.py）在 run_python 上的行为。

覆盖手动确认（approve / reject / sender 不可用 / 取消）、auto_approve 放行、
以及 LangChain run_manager 注入穿透装饰器（functools.wraps 保留签名）。
"""

import asyncio
import inspect
from typing import Any

import pytest

from api.agent import interaction
from tools import confirm as confirm_module
from tools.system import tool_python as tool_module
from tools.system.tool_python import RunPythonTool


class FakeSender:
    """最小发送器替身：记录 ask_user 调用参数，供断言确认载荷。"""

    def __init__(self) -> None:
        self.asked_kwargs: dict[str, Any] | None = None

    async def ask_user(self, **kwargs: Any) -> None:
        self.asked_kwargs = kwargs


def _patch_sender(monkeypatch: pytest.MonkeyPatch, sender: object) -> None:
    """把 confirm_module.ToolSender.from_context 替换为返回 sender。"""
    monkeypatch.setattr(
        confirm_module,
        "ToolSender",
        type("TS", (), {"from_context": staticmethod(lambda: sender)}),
    )


def _capture_register(monkeypatch: pytest.MonkeyPatch, recorded: dict[str, Any]) -> None:
    """拦截 interaction.register，记录 interaction_id 与 future 供外部 resolve。"""
    real_register = interaction.register

    def patched_register() -> tuple[str, asyncio.Future]:
        iid, fut = real_register()
        recorded["id"] = iid
        recorded["future"] = fut
        return iid, fut

    monkeypatch.setattr(interaction, "register", patched_register)


# ── 手动确认路径 ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_confirm_approve_executes_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """用户 approve 后执行代码；ask_user 载荷携带 code / mode / approve_text / reject_text / tool_name。"""
    interaction.current_session_id.set("")  # 非 auto_approve → 走手动确认

    fake = FakeSender()
    _patch_sender(monkeypatch, fake)
    recorded: dict[str, Any] = {}
    _capture_register(monkeypatch, recorded)

    task = asyncio.create_task(RunPythonTool()._arun(code="print('approved')"))
    await asyncio.sleep(0)  # 让 _arun 执行到 await future

    assert fake.asked_kwargs is not None
    assert fake.asked_kwargs["mode"] == "confirm"
    assert fake.asked_kwargs["approve_text"] == "执行"
    assert fake.asked_kwargs["reject_text"] == "取消"
    assert fake.asked_kwargs["code"] == "print('approved')"
    assert fake.asked_kwargs["tool_name"] == "run_python"

    assert interaction.resolve(recorded["id"], {"action": "approve", "reason": ""}) is True
    result = await asyncio.wait_for(task, timeout=5)

    assert "approved" in result  # 批准后真正执行并返回 stdout


@pytest.mark.asyncio
async def test_confirm_reject_with_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    """用户拒绝并附原因：返回统一拒绝错误且包含原因文本。"""
    interaction.current_session_id.set("")

    fake = FakeSender()
    _patch_sender(monkeypatch, fake)
    recorded: dict[str, Any] = {}
    _capture_register(monkeypatch, recorded)

    task = asyncio.create_task(RunPythonTool()._arun(code="print('x')"))
    await asyncio.sleep(0)

    assert interaction.resolve(recorded["id"], {"action": "reject", "reason": "不想跑"}) is True
    result = await asyncio.wait_for(task, timeout=1)

    assert "拒绝执行代码" in result
    assert "不想跑" in result


@pytest.mark.asyncio
async def test_confirm_sender_none_returns_websocket_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """WebSocket 上下文不可用时，手动确认分支返回连接错误而非执行。"""
    interaction.current_session_id.set("")
    monkeypatch.setattr(
        confirm_module,
        "ToolSender",
        type("TS", (), {"from_context": staticmethod(lambda: None)}),
    )

    result = await RunPythonTool()._arun(code="print('x')")

    assert "WebSocket 连接不可用" in result


@pytest.mark.asyncio
async def test_confirm_cancelled_returns_cancel_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """等待期间未来被取消（任务取消）→ 返回统一取消错误。"""
    interaction.current_session_id.set("")

    fake = FakeSender()
    _patch_sender(monkeypatch, fake)
    recorded: dict[str, Any] = {}
    _capture_register(monkeypatch, recorded)

    task = asyncio.create_task(RunPythonTool()._arun(code="print('x')"))
    await asyncio.sleep(0)

    recorded["future"].cancel()  # 模拟用户取消整个回复
    result = await asyncio.wait_for(task, timeout=1)

    assert "用户取消了回复" in result


# ── auto_approve 放行路径 ───────────────────────────────────


@pytest.mark.asyncio
async def test_auto_approve_bypasses_ask(monkeypatch: pytest.MonkeyPatch) -> None:
    """会话开启 auto_approve 时直接执行，不调用 ask_user。"""
    sid = "confirm-bypass"
    interaction.current_session_id.set(sid)
    interaction.set_session_auto_approve(sid, True)

    fake = FakeSender()
    _patch_sender(monkeypatch, fake)
    try:
        result = await RunPythonTool()._arun(code="print('bypass')")
        assert "bypass" in result
        assert fake.asked_kwargs is None  # 未触发确认
    finally:
        interaction.clear_session_settings(sid)
        interaction.current_session_id.set("")


# ── 签名护栏：run_manager 注入穿透 ──────────────────────────


def test_arun_signature_advertises_run_manager() -> None:
    """_arun 经类装饰器包装但 wraps 保留签名（run_manager 仍被 LangChain 注入），并保留 __wrapped__。"""
    sig = inspect.signature(RunPythonTool._arun)
    assert "run_manager" in sig.parameters
    assert RunPythonTool._arun.__wrapped__ is not None


@pytest.mark.asyncio
async def test_langchain_injects_run_manager_through_decorator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """端到端:经 BaseTool.ainvoke 调用,run_manager 注入并穿透装饰器实现流式。"""
    sid = "confirm-inject"
    interaction.current_session_id.set(sid)
    interaction.set_session_auto_approve(sid, True)

    fake = FakeSender()
    # 流式路径由 tool_python 命名空间读取 ToolSender（_arun 内读取）
    monkeypatch.setattr(
        tool_module,
        "ToolSender",
        type("TS", (), {"from_context": staticmethod(lambda: fake)}),
    )
    try:
        result = await RunPythonTool().ainvoke({"code": "print('injected')"})
        assert "injected" in result  # 输出经流式子进程返回
    finally:
        interaction.clear_session_settings(sid)
        interaction.current_session_id.set("")
