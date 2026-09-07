"""@path_guard 装饰器单测。

覆盖：守卫先于确认弹窗/后台 spawn、相位序（空值→访问→存在/类型）、静默默认目录
解析、规范文案，以及业务卫语句在收编后仍保留。
"""

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tools import confirm as confirm_module
from tools.files.tool_file_create_directory import FileCreateDirectoryTool
from tools.files.tool_file_edit import FileEditTool
from tools.files.tool_file_list_directory import FileListDirectoryTool
from tools.files.tool_file_read import FileReadTool
from tools.files.tool_file_rename import FileRenameTool
from tools.files.tool_file_search import FileSearchTool
from tools.files.tool_file_search_text import FileSearchTextTool
from tools.files.tool_file_write import FileWriteTool


@pytest.fixture
def whitelist_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """把 tmp_path 加入路径白名单，使工具可通过安全访问校验。"""
    monkeypatch.setattr(
        "tools.base._load_path_whitelist",
        lambda: [(str(tmp_path), True)],
    )
    return tmp_path


def _error(result: str) -> str:
    """解析工具返回的 JSON，返回 error 文本。"""
    return str(json.loads(result)["error"])


class FakeSender:
    """记录 ask_user 调用参数的最小发送器替身。"""

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


# ── 空值（required）────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_required_read(whitelist_tmp: Path) -> None:
    result = await FileReadTool()._arun(file_path="")
    assert "file_path" in _error(result)


@pytest.mark.asyncio
async def test_empty_required_create_directory() -> None:
    result = await FileCreateDirectoryTool()._arun(directory_path="")
    assert "directory_path" in _error(result)


@pytest.mark.asyncio
async def test_rename_empty_prefers_file_path() -> None:
    """两路径皆空时按 spec 顺序报 file_path。"""
    result = await FileRenameTool()._arun(file_path="", new_path="")
    assert "file_path" in _error(result)


@pytest.mark.asyncio
async def test_rename_empty_new_path_after_file_path() -> None:
    result = await FileRenameTool()._arun(file_path="x", new_path="")
    assert "new_path" in _error(result)


# ── 安全访问：白名单 / SonettoBlocker ──────────────────────────


@pytest.mark.asyncio
async def test_access_denied_when_whitelist_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """白名单为空 → 即便是已存在文件也拒绝访问。"""
    monkeypatch.setattr("tools.base._load_path_whitelist", list)
    target = tmp_path / "a.txt"
    target.write_text("x", encoding="utf-8")
    result = await FileReadTool()._arun(file_path=str(target))
    assert "白名单" in _error(result)


@pytest.mark.asyncio
async def test_blocker_returns_single_merged_text(whitelist_tmp: Path) -> None:
    """目录内放 SonettoBlocker 标记 → 返回合并版统一阻断文案。"""
    (whitelist_tmp / "SonettoBlocker").write_text("", encoding="utf-8")
    target = whitelist_tmp / "a.txt"
    target.write_text("x", encoding="utf-8")
    result = await FileReadTool()._arun(file_path=str(target))
    assert "在以下目录中发现了 SonettoBlocker 文件" in _error(result)


# ── 存在 / 类型（file/dir）────────────────────────────────


@pytest.mark.asyncio
async def test_exists_missing_file(whitelist_tmp: Path) -> None:
    result = await FileReadTool()._arun(file_path=str(whitelist_tmp / "nope.txt"))
    assert "文件不存在" in _error(result)


@pytest.mark.asyncio
async def test_type_dir_is_not_file(whitelist_tmp: Path) -> None:
    result = await FileReadTool()._arun(file_path=str(whitelist_tmp))
    assert "路径不是文件" in _error(result)


@pytest.mark.asyncio
async def test_exists_missing_dir(whitelist_tmp: Path) -> None:
    result = await FileListDirectoryTool()._arun(
        directory_path=str(whitelist_tmp / "nope")
    )
    assert "目录不存在" in _error(result)


@pytest.mark.asyncio
async def test_type_file_is_not_dir(whitelist_tmp: Path) -> None:
    target = whitelist_tmp / "a.txt"
    target.write_text("x", encoding="utf-8")
    result = await FileListDirectoryTool()._arun(directory_path=str(target))
    assert "路径不是目录" in _error(result)


# ── 多路径相位序（rename）─────────────────────────────────


@pytest.mark.asyncio
async def test_rename_target_exists(whitelist_tmp: Path) -> None:
    """源存在且目标已存在 → 报目标已存在（回归）。"""
    src = whitelist_tmp / "old.txt"
    dst = whitelist_tmp / "new.txt"
    src.write_text("x", encoding="utf-8")
    dst.write_text("y", encoding="utf-8")
    result = await FileRenameTool()._arun(
        file_path=str(src), new_path=str(dst)
    )
    assert "目标已存在" in _error(result)


@pytest.mark.asyncio
async def test_rename_source_missing_beats_target_exists(whitelist_tmp: Path) -> None:
    """源缺失与目标已存在并存 → 相位序使源缺失（文件不存在）先报。"""
    dst = whitelist_tmp / "new.txt"
    dst.write_text("y", encoding="utf-8")
    result = await FileRenameTool()._arun(
        file_path=str(whitelist_tmp / "missing.txt"), new_path=str(dst)
    )
    assert "文件不存在" in _error(result)
    assert "目标已存在" not in _error(result)


# ── 静默默认目录（空参 → "."）──────────────────────────────


@pytest.mark.asyncio
async def test_list_directory_empty_resolves_cwd(whitelist_tmp: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(whitelist_tmp)
    (whitelist_tmp / "a.txt").write_text("x", encoding="utf-8")
    result = await FileListDirectoryTool()._arun(directory_path="")
    data = json.loads(result)["data"]
    assert data["directory"] == os.path.abspath(".")


@pytest.mark.asyncio
async def test_search_empty_directory_resolves_cwd(whitelist_tmp: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(whitelist_tmp)
    (whitelist_tmp / "a.txt").write_text("x", encoding="utf-8")
    result = await FileSearchTool()._arun(search_pattern="*.txt")
    data = json.loads(result)["data"]
    assert data["count"] == 1


# ── 与 confirm / background 的组合（守卫先于弹窗 / spawn）────


@pytest.mark.asyncio
async def test_guard_runs_before_confirm_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """非法路径在确认弹窗前即被拒：不触发 ask_user。"""
    fake = FakeSender()
    _patch_sender(monkeypatch, fake)
    result = await FileWriteTool()._arun(file_path="", content="x")
    assert "file_path" in _error(result)
    assert fake.asked_kwargs is None


@pytest.mark.asyncio
async def test_guard_runs_before_background_spawn(whitelist_tmp: Path) -> None:
    """无效目录在转入后台前即被拒：不返回 task_index。"""
    result = await FileSearchTool()._arun(
        search_pattern="*.py",
        directory_path=str(whitelist_tmp / "missing"),
        background=True,
    )
    payload = json.loads(result)
    assert payload.get("success") is False
    assert "目录不存在" in payload["error"]
    assert "task_index" not in payload.get("data", {})


# ── 业务卫语句在收编后仍保留（直接驱动 sync 身体）────────────


def test_business_guard_write_content() -> None:
    result = FileWriteTool()._run_impl(file_path="x", content="")
    assert "content" in _error(result)


def test_business_guard_edit_edits() -> None:
    result = FileEditTool()._run_impl(file_path="x", edits="")
    assert "edits" in _error(result)


def test_business_guard_search_text_bad_regex() -> None:
    result = FileSearchTextTool()._run_impl(
        file_path="x", pattern="[unclosed", case_insensitive=False
    )
    assert "正则表达式错误" in _error(result)
