"""@path_guard 内置 sudo 越权的单测。

覆盖：sudo 仅在安全访问被阻断且 sudo=True 时触发、批准后仅跳过安全访问、
拒绝/取消/sender 不可用的错误形态、路径本就允许时 sudo 不打扰用户，以及
「先 sudo 授权、后侵彻性文件操作确认」的多确认顺序（file_delete 双气泡）。
"""

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from api.agent import interaction
from tools import confirm as confirm_module
from tools import path_guard as path_guard_module
from tools.files.tool_file_delete import FileDeleteTool
from tools.files.tool_file_read import FileReadTool


@pytest.fixture
def deny_all(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """白名单为空 → 任何路径都被安全访问阻断（可被 sudo 越过）。"""
    monkeypatch.setattr("tools.base._load_path_whitelist", list)
    return tmp_path


class FakeSender:
    """记录每次 ask_user 调用的最小发送器替身。"""

    def __init__(self) -> None:
        self.asked: list[dict[str, Any]] = []

    async def ask_user(self, **kwargs: Any) -> None:
        self.asked.append(kwargs)


def _patch_senders(monkeypatch: pytest.MonkeyPatch, sender: FakeSender) -> None:
    """让 path_guard（sudo）与 confirm（操作确认）两条路径共用同一替身。

    两个模块各自持有 ToolSender 引用，需分别替换其 from_context。
    """
    fake_cls = type("TS", (), {"from_context": staticmethod(lambda: sender)})
    monkeypatch.setattr(path_guard_module, "ToolSender", fake_cls)
    monkeypatch.setattr(confirm_module, "ToolSender", fake_cls)


def _capture_registers(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, asyncio.Future]]:
    """拦截 interaction.register，记录每次的 (interaction_id, future)。"""
    recorded: list[tuple[str, asyncio.Future]] = []
    real_register = interaction.register

    def patched_register() -> tuple[str, asyncio.Future]:
        iid, fut = real_register()
        recorded.append((iid, fut))
        return iid, fut

    monkeypatch.setattr(interaction, "register", patched_register)
    return recorded


def _error(result: str) -> str:
    return str(json.loads(result)["error"])


def _response(action: str, reason: str = "") -> dict[str, str]:
    return {"action": action, "reason": reason}


async def _wait_n_asked(
    task: asyncio.Task[Any], sender: FakeSender, n: int, timeout: float = 5.0
) -> None:
    """等待累计出现第 n 次 ask_user（sudo/confirm 间有 off_thread 往返与逐层等待）。"""
    async with asyncio.timeout(timeout):
        while len(sender.asked) < n:
            if task.done():
                break
            await asyncio.sleep(0.01)
    assert len(sender.asked) >= n


# ── sudo 批准后仅跳过安全访问 → 继续执行 ─────────────────────


@pytest.mark.asyncio
async def test_sudo_approve_bypasses_access(
    deny_all: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """白名单为空读取被阻断；sudo=True + 批准 → 文件正常读出。"""
    target = deny_all / "a.txt"
    target.write_text("hello", encoding="utf-8")

    sender = FakeSender()
    _patch_senders(monkeypatch, sender)
    recorded = _capture_registers(monkeypatch)

    task = asyncio.create_task(FileReadTool()._arun(file_path=str(target), sudo=True))
    await _wait_n_asked(task, sender, 1)
    assert sender.asked[0]["mode"] == "sudo"
    assert sender.asked[0]["approve_text"] == "sudo 授权"

    assert interaction.resolve(recorded[0][0], _response("approve")) is True
    result = await asyncio.wait_for(task, timeout=5)

    assert json.loads(result).get("success") is True
    assert json.loads(result)["data"]["content"] == "hello"


@pytest.mark.asyncio
async def test_sudo_approve_still_enforces_existence(
    deny_all: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """sudo 只跳过安全访问：文件不存在仍报「文件不存在」。"""
    missing = deny_all / "missing.txt"

    sender = FakeSender()
    _patch_senders(monkeypatch, sender)
    recorded = _capture_registers(monkeypatch)

    task = asyncio.create_task(FileReadTool()._arun(file_path=str(missing), sudo=True))
    await _wait_n_asked(task, sender, 1)
    assert interaction.resolve(recorded[0][0], _response("approve")) is True
    result = await asyncio.wait_for(task, timeout=5)

    assert "文件不存在" in _error(result)


# ── sudo 拒绝 / 取消 / sender 不可用 ─────────────────────────


@pytest.mark.asyncio
async def test_sudo_reject_returns_error(
    deny_all: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = deny_all / "a.txt"
    target.write_text("x", encoding="utf-8")

    sender = FakeSender()
    _patch_senders(monkeypatch, sender)
    recorded = _capture_registers(monkeypatch)

    task = asyncio.create_task(FileReadTool()._arun(file_path=str(target), sudo=True))
    await _wait_n_asked(task, sender, 1)
    assert interaction.resolve(recorded[0][0], _response("reject", "不想越权")) is True
    result = await asyncio.wait_for(task, timeout=5)

    assert "用户拒绝了 sudo 越权授权" in _error(result)
    assert "不想越权" in _error(result)


@pytest.mark.asyncio
async def test_sudo_cancelled_returns_cancel_message(
    deny_all: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = deny_all / "a.txt"
    target.write_text("x", encoding="utf-8")

    sender = FakeSender()
    _patch_senders(monkeypatch, sender)
    recorded = _capture_registers(monkeypatch)

    task = asyncio.create_task(FileReadTool()._arun(file_path=str(target), sudo=True))
    await _wait_n_asked(task, sender, 1)
    recorded[0][1].cancel()
    result = await asyncio.wait_for(task, timeout=5)

    assert "用户取消了回复" in _error(result)


@pytest.mark.asyncio
async def test_sudo_sender_none_returns_websocket_error(
    deny_all: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ToolSender 上下文缺失（无 ws）→ sudo 提示前即返回连接错误。"""
    target = deny_all / "a.txt"
    target.write_text("x", encoding="utf-8")
    none_cls = type("TS", (), {"from_context": staticmethod(lambda: None)})
    monkeypatch.setattr(path_guard_module, "ToolSender", none_cls)

    result = await FileReadTool()._arun(file_path=str(target), sudo=True)

    assert "WebSocket 连接不可用" in _error(result)


# ── 触发条件：仅在访问被阻断时弹出；路径允许时 sudo 不打扰 ──


@pytest.mark.asyncio
async def test_sudo_ignored_when_path_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """路径本就允许（白名单放行）时，sudo=True 也不弹气泡，直接成功。"""
    monkeypatch.setattr(
        "tools.base._load_path_whitelist",
        lambda: [(str(tmp_path), True)],
    )
    target = tmp_path / "a.txt"
    target.write_text("ok", encoding="utf-8")

    sender = FakeSender()
    _patch_senders(monkeypatch, sender)

    result = await FileReadTool()._arun(file_path=str(target), sudo=True)

    assert sender.asked == []
    assert json.loads(result).get("success") is True


# ── 多确认顺序：先 sudo，再侵彻性文件操作 ───────────────────


@pytest.mark.asyncio
async def test_sudo_then_operation_confirm_order(
    deny_all: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """file_delete 双气泡：第一枚 sudo，第二枚文件删除确认，两次都批准后删除。"""
    target = deny_all / "victim.txt"
    target.write_text("x", encoding="utf-8")

    sender = FakeSender()
    _patch_senders(monkeypatch, sender)
    recorded = _capture_registers(monkeypatch)

    task = asyncio.create_task(FileDeleteTool()._arun(file_path=str(target), sudo=True))

    # 第 1 枚 = sudo 授权
    await _wait_n_asked(task, sender, 1)
    assert sender.asked[0]["mode"] == "sudo"
    assert "sudo" not in sender.asked[0]  # sudo 已消费，不进载荷
    assert interaction.resolve(recorded[0][0], _response("approve")) is True

    # 第 2 枚 = 侵彻性文件删除操作确认（sudo 之后才出现）
    await _wait_n_asked(task, sender, 2)
    assert sender.asked[1]["mode"] == "confirm"
    assert sender.asked[1]["tool_name"] == "file_delete"
    assert interaction.resolve(recorded[1][0], _response("approve")) is True

    result = await asyncio.wait_for(task, timeout=5)
    assert json.loads(result).get("success") is True
    assert not target.exists()  # 两次批准后真正删除


@pytest.mark.asyncio
async def test_sudo_reject_stops_before_operation_confirm(
    deny_all: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """sudo 被拒 → 不会进入文件删除的操作确认，更不会执行。"""
    target = deny_all / "victim.txt"
    target.write_text("x", encoding="utf-8")

    sender = FakeSender()
    _patch_senders(monkeypatch, sender)
    recorded = _capture_registers(monkeypatch)

    task = asyncio.create_task(FileDeleteTool()._arun(file_path=str(target), sudo=True))
    await _wait_n_asked(task, sender, 1)
    assert sender.asked[0]["mode"] == "sudo"
    assert interaction.resolve(recorded[0][0], _response("reject", "别动")) is True

    result = await asyncio.wait_for(task, timeout=5)
    await asyncio.sleep(0.02)  # 若错误地在拒绝后仍发第二枚，让其有时间落地
    assert len(sender.asked) == 1  # 只有 sudo 一枚，未触发操作确认
    assert "用户拒绝" in _error(result)
    assert target.exists()  # 未删除
