"""测试四个 file 工具的执行前确认（confirm_execution 门控）。

覆盖手动确认（approve 真正执行 / reject 返回拒绝错误 / sender 不可用 /
确认载荷断言）、auto_approve 直接放行,对五个写入/破坏性工具参数化:
file_write / file_edit / file_delete / file_create_directory / file_rename。
"""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from api.agent import interaction
from tools import confirm as confirm_module
from tools.files.tool_file_create_directory import FileCreateDirectoryTool
from tools.files.tool_file_delete import FileDeleteTool
from tools.files.tool_file_edit import FileEditTool
from tools.files.tool_file_rename import FileRenameTool
from tools.files.tool_file_write import FileWriteTool


@pytest.fixture
def whitelist_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """把 tmp_path 加入路径白名单，使工具可通过安全检查。"""
    monkeypatch.setattr(
        "tools.base._load_path_whitelist",
        lambda: [(str(tmp_path), True)],
    )
    return tmp_path


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


# ── 工具用例表：调用工厂 / 前置文件 / 期望载荷 / 文案 ──────


def _edit_json() -> str:
    return json.dumps([{"old_string": "foo", "new_string": "FOO"}])


TOOL_CASES: list[dict[str, Any]] = [
    {
        "name": "file_write",
        "call": lambda p: FileWriteTool()._arun(
            file_path=str(p / "a.txt"), content="hi"
        ),
        "setup": lambda p: None,
        "expected_payload": lambda p: {
            "file_path": str(p / "a.txt"),
            "content": "hi",
        },
        "options": ["允许写入", "拒绝"],
        "reject_message": "用户拒绝写入文件",
        "side_effect_check": lambda p, approved: (
            (p / "a.txt").exists() == approved
        ),
    },
    {
        "name": "file_delete",
        "call": lambda p: FileDeleteTool()._arun(file_path=str(p / "a.txt")),
        "setup": lambda p: (p / "a.txt").write_text("x", encoding="utf-8"),
        "expected_payload": lambda p: {"file_path": str(p / "a.txt")},
        "options": ["允许删除", "拒绝"],
        "reject_message": "用户拒绝删除文件",
        "side_effect_check": lambda p, approved: (
            (p / "a.txt").exists() == (not approved)
        ),
    },
    {
        "name": "file_create_directory",
        "call": lambda p: FileCreateDirectoryTool()._arun(
            directory_path=str(p / "newdir")
        ),
        "setup": lambda p: None,
        "expected_payload": lambda p: {"directory_path": str(p / "newdir")},
        "options": ["允许创建", "拒绝"],
        "reject_message": "用户拒绝创建目录",
        "side_effect_check": lambda p, approved: (
            (p / "newdir").is_dir() == approved
        ),
    },
    {
        "name": "file_rename",
        "call": lambda p: FileRenameTool()._arun(
            file_path=str(p / "old.txt"), new_path=str(p / "new.txt")
        ),
        "setup": lambda p: (p / "old.txt").write_text("x", encoding="utf-8"),
        "expected_payload": lambda p: {
            "file_path": str(p / "old.txt"),
            "new_path": str(p / "new.txt"),
        },
        "options": ["允许重命名", "拒绝"],
        "reject_message": "用户拒绝重命名文件",
        "side_effect_check": lambda p, approved: (
            (p / "new.txt").exists() == approved
        ),
    },
    {
        "name": "file_edit",
        "call": lambda p: FileEditTool()._arun(
            file_path=str(p / "a.txt"), edits=_edit_json()
        ),
        "setup": lambda p: (p / "a.txt").write_text("foo", encoding="utf-8"),
        "expected_payload": lambda p: {
            "file_path": str(p / "a.txt"),
            "edits": _edit_json(),
        },
        "options": ["允许编辑", "拒绝"],
        "reject_message": "用户拒绝编辑文件",
        "side_effect_check": lambda p, approved: (
            (p / "a.txt").read_text(encoding="utf-8") == ("FOO" if approved else "foo")
        ),
    },
]


# ── 手动确认路径 ────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", TOOL_CASES, ids=[c["name"] for c in TOOL_CASES]
)
async def test_confirm_approve_executes(
    whitelist_tmp: Path, monkeypatch: pytest.MonkeyPatch, case: dict[str, Any]
) -> None:
    """用户 approve 后真正执行；ask_user 载荷携带 mode/options/附加字段。"""
    interaction.current_session_id.set("")  # 非 auto_approve → 走手动确认
    case["setup"](whitelist_tmp)

    fake = FakeSender()
    _patch_sender(monkeypatch, fake)
    recorded: dict[str, Any] = {}
    _capture_register(monkeypatch, recorded)

    task = asyncio.create_task(case["call"](whitelist_tmp))
    await asyncio.sleep(0)  # 让 _arun 执行到 await future

    assert fake.asked_kwargs is not None
    assert fake.asked_kwargs["mode"] == "confirm"
    assert fake.asked_kwargs["tool_name"] == case["name"]
    assert fake.asked_kwargs["options"] == case["options"]
    for key, value in case["expected_payload"](whitelist_tmp).items():
        assert fake.asked_kwargs[key] == value

    assert interaction.resolve(recorded["id"], {"action": "approve", "reason": ""}) is True
    result = await asyncio.wait_for(task, timeout=5)

    assert json.loads(result).get("success") is True
    assert case["side_effect_check"](whitelist_tmp, True)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", TOOL_CASES, ids=[c["name"] for c in TOOL_CASES]
)
async def test_confirm_reject_with_reason(
    whitelist_tmp: Path, monkeypatch: pytest.MonkeyPatch, case: dict[str, Any]
) -> None:
    """用户拒绝并附原因：返回统一拒绝错误且包含原因，未产生副作用。"""
    interaction.current_session_id.set("")
    case["setup"](whitelist_tmp)

    fake = FakeSender()
    _patch_sender(monkeypatch, fake)
    recorded: dict[str, Any] = {}
    _capture_register(monkeypatch, recorded)

    task = asyncio.create_task(case["call"](whitelist_tmp))
    await asyncio.sleep(0)

    assert interaction.resolve(recorded["id"], {"action": "reject", "reason": "不想操作"}) is True
    result = await asyncio.wait_for(task, timeout=1)

    assert case["reject_message"] in result
    assert "不想操作" in result
    assert case["side_effect_check"](whitelist_tmp, False)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", TOOL_CASES, ids=[c["name"] for c in TOOL_CASES]
)
async def test_confirm_sender_none_returns_websocket_error(
    whitelist_tmp: Path, monkeypatch: pytest.MonkeyPatch, case: dict[str, Any]
) -> None:
    """WebSocket 上下文不可用时，手动确认分支返回连接错误而非执行。"""
    interaction.current_session_id.set("")
    case["setup"](whitelist_tmp)
    monkeypatch.setattr(
        confirm_module,
        "ToolSender",
        type("TS", (), {"from_context": staticmethod(lambda: None)}),
    )

    result = await case["call"](whitelist_tmp)

    assert "WebSocket 连接不可用" in result
    assert case["side_effect_check"](whitelist_tmp, False)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", TOOL_CASES, ids=[c["name"] for c in TOOL_CASES]
)
async def test_confirm_cancelled_returns_cancel_message(
    whitelist_tmp: Path, monkeypatch: pytest.MonkeyPatch, case: dict[str, Any]
) -> None:
    """等待期间未来被取消（任务取消）→ 返回统一取消错误。"""
    interaction.current_session_id.set("")
    case["setup"](whitelist_tmp)

    fake = FakeSender()
    _patch_sender(monkeypatch, fake)
    recorded: dict[str, Any] = {}
    _capture_register(monkeypatch, recorded)

    task = asyncio.create_task(case["call"](whitelist_tmp))
    await asyncio.sleep(0)

    recorded["future"].cancel()  # 模拟用户取消整个回复
    result = await asyncio.wait_for(task, timeout=1)

    assert "用户取消了回复" in result
    assert case["side_effect_check"](whitelist_tmp, False)


# ── auto_approve 放行路径 ───────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", TOOL_CASES, ids=[c["name"] for c in TOOL_CASES]
)
async def test_auto_approve_bypasses_ask(
    whitelist_tmp: Path, monkeypatch: pytest.MonkeyPatch, case: dict[str, Any]
) -> None:
    """会话开启 auto_approve 时直接执行，不调用 ask_user。"""
    sid = "file-confirm-bypass"
    interaction.current_session_id.set(sid)
    interaction.set_session_auto_approve(sid, True)
    case["setup"](whitelist_tmp)

    fake = FakeSender()
    _patch_sender(monkeypatch, fake)
    try:
        result = await case["call"](whitelist_tmp)
        assert json.loads(result).get("success") is True
        assert fake.asked_kwargs is None  # 未触发确认
        assert case["side_effect_check"](whitelist_tmp, True)
    finally:
        interaction.clear_session_settings(sid)
        interaction.current_session_id.set("")
