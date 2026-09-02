"""测试拆解后的 file 系列工具（单一职责）。

覆盖 file_write / file_delete / file_rename / file_create_directory /
file_list_directory / file_search / file_edit / file_search_text 的成功与错误路径,
以及 get_all_tools 注册表断言（包含全部新工具、不含已删除的 file_manage）。

写入/编辑/删除/建目录四个工具已接入执行前确认,改用 async ``_arun`` 全路径测试
（以会话级 auto_approve 放行,跳过确认门控直接覆盖前置校验 + 操作逻辑）;
其余只读/重命名工具保持同步 ``_run`` 测试。
"""

import json
from pathlib import Path
from typing import Any

import pytest

from api.agent import interaction
from tools import get_all_tools
from tools.files.tool_file_create_directory import FileCreateDirectoryTool
from tools.files.tool_file_delete import FileDeleteTool
from tools.files.tool_file_edit import FileEditTool
from tools.files.tool_file_list_directory import FileListDirectoryTool
from tools.files.tool_file_rename import FileRenameTool
from tools.files.tool_file_search import FileSearchTool
from tools.files.tool_file_search_text import FileSearchTextTool
from tools.files.tool_file_write import FileWriteTool


@pytest.fixture
def whitelist_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """把 tmp_path 加入路径白名单，使工具可通过安全检查。"""
    monkeypatch.setattr(
        "tools.base._load_path_whitelist",
        lambda: [(str(tmp_path), True)],
    )
    return tmp_path


async def _auto_approve(coro: Any) -> str:
    """在 auto_approve 会话下 await 一次 _arun（跳过确认，覆盖前置校验 + 操作）。"""
    sid = "file-auto-approve"
    interaction.current_session_id.set(sid)
    interaction.set_session_auto_approve(sid, True)
    try:
        return await coro
    finally:
        interaction.clear_session_settings(sid)
        interaction.current_session_id.set("")


def _success_data(result: str) -> dict:
    """解析 format_success 的 JSON，返回 data 字段。"""
    parsed = json.loads(result)
    assert parsed.get("success") is True, parsed
    return parsed["data"]


def _error_msg(result: str) -> str:
    """解析 format_error 的 JSON，返回 error 文本。"""
    parsed = json.loads(result)
    assert parsed.get("success") is False, parsed
    return parsed["error"]


# ── file_write（执行前确认） ───────────────────────────────


@pytest.mark.asyncio
async def test_file_write(whitelist_tmp: Path) -> None:
    p = whitelist_tmp / "sub" / "a.txt"

    result = await _auto_approve(
        FileWriteTool()._arun(file_path=str(p), content="hello")
    )
    data = _success_data(result)

    assert p.read_text(encoding="utf-8") == "hello"
    assert data["line_count"] == 1


@pytest.mark.asyncio
async def test_file_write_empty_path(whitelist_tmp: Path) -> None:
    result = await _auto_approve(FileWriteTool()._arun(file_path="", content="x"))
    assert "file_path" in _error_msg(result)


@pytest.mark.asyncio
async def test_file_write_empty_content(whitelist_tmp: Path) -> None:
    result = await _auto_approve(
        FileWriteTool()._arun(file_path=str(whitelist_tmp / "a.txt"))
    )
    assert "content" in _error_msg(result)


# ── file_delete（执行前确认） ──────────────────────────────


@pytest.mark.asyncio
async def test_file_delete_file(whitelist_tmp: Path) -> None:
    p = whitelist_tmp / "a.txt"
    p.write_text("x", encoding="utf-8")

    result = await _auto_approve(FileDeleteTool()._arun(file_path=str(p)))
    data = _success_data(result)

    assert not p.exists()
    assert "已删除" in data["message"]


@pytest.mark.asyncio
async def test_file_delete_directory(whitelist_tmp: Path) -> None:
    d = whitelist_tmp / "dir"
    d.mkdir()
    (d / "f.txt").write_text("x", encoding="utf-8")

    result = await _auto_approve(FileDeleteTool()._arun(file_path=str(d)))
    _success_data(result)

    assert not d.exists()


@pytest.mark.asyncio
async def test_file_delete_missing(whitelist_tmp: Path) -> None:
    result = await _auto_approve(
        FileDeleteTool()._arun(file_path=str(whitelist_tmp / "nope.txt"))
    )
    assert "文件不存在" in _error_msg(result)


# ── file_rename（保持同步，无确认） ────────────────────────


def test_file_rename(whitelist_tmp: Path) -> None:
    src = whitelist_tmp / "old.txt"
    src.write_text("x", encoding="utf-8")
    dst = whitelist_tmp / "new.txt"

    result = FileRenameTool()._run(file_path=str(src), new_path=str(dst))
    data = _success_data(result)

    assert not src.exists()
    assert dst.exists()
    assert data["new_path"] == str(dst)


def test_file_rename_target_exists(whitelist_tmp: Path) -> None:
    src = whitelist_tmp / "old.txt"
    src.write_text("x", encoding="utf-8")
    dst = whitelist_tmp / "new.txt"
    dst.write_text("y", encoding="utf-8")

    result = FileRenameTool()._run(file_path=str(src), new_path=str(dst))
    assert "目标已存在" in _error_msg(result)


# ── file_create_directory（执行前确认） ────────────────────


@pytest.mark.asyncio
async def test_file_create_directory(whitelist_tmp: Path) -> None:
    d = whitelist_tmp / "x" / "y"

    result = await _auto_approve(
        FileCreateDirectoryTool()._arun(directory_path=str(d))
    )
    data = _success_data(result)

    assert d.is_dir()
    assert "目录已创建" in data["message"]


@pytest.mark.asyncio
async def test_file_create_directory_empty(whitelist_tmp: Path) -> None:
    result = await _auto_approve(FileCreateDirectoryTool()._arun(directory_path=""))
    assert "directory_path" in _error_msg(result)


# ── file_list_directory（保持同步） ────────────────────────


def test_file_list_directory(whitelist_tmp: Path) -> None:
    (whitelist_tmp / "a.txt").write_text("a", encoding="utf-8")
    (whitelist_tmp / "sub").mkdir()

    result = FileListDirectoryTool()._run(directory_path=str(whitelist_tmp))
    data = _success_data(result)

    assert data["count"] == 2
    assert data["file_count"] == 1
    assert data["dir_count"] == 1


# ── file_search（glob，保持同步） ──────────────────────────


def test_file_search_glob(whitelist_tmp: Path) -> None:
    (whitelist_tmp / "a.txt").write_text("a", encoding="utf-8")
    (whitelist_tmp / "b.py").write_text("b", encoding="utf-8")

    result = FileSearchTool()._run(
        search_pattern="*.txt", directory_path=str(whitelist_tmp)
    )
    data = _success_data(result)

    assert data["count"] == 1
    assert data["found_files"][0]["name"] == "a.txt"


# ── file_edit（执行前确认） ────────────────────────────────


@pytest.mark.asyncio
async def test_file_edit_batch(whitelist_tmp: Path) -> None:
    p = whitelist_tmp / "a.txt"
    p.write_text("foo bar foo", encoding="utf-8")
    edits = json.dumps([
        {"old_string": "foo", "new_string": "FOO", "replace_all": True},
        {"old_string": "bar", "new_string": "BAZ"},
    ])

    result = await _auto_approve(
        FileEditTool()._arun(file_path=str(p), edits=edits)
    )
    data = _success_data(result)

    assert data["total_edits"] == 2
    assert data["success_count"] == 2
    assert data["failed_count"] == 0
    assert p.read_text(encoding="utf-8") == "FOO BAZ FOO"


@pytest.mark.asyncio
async def test_file_edit_single_in_list(whitelist_tmp: Path) -> None:
    p = whitelist_tmp / "a.txt"
    p.write_text("hello world", encoding="utf-8")
    edits = json.dumps([{"old_string": "world", "new_string": "there"}])

    result = await _auto_approve(
        FileEditTool()._arun(file_path=str(p), edits=edits)
    )
    data = _success_data(result)

    assert data["total_edits"] == 1
    assert data["success_count"] == 1
    assert p.read_text(encoding="utf-8") == "hello there"


@pytest.mark.asyncio
async def test_file_edit_no_match(whitelist_tmp: Path) -> None:
    p = whitelist_tmp / "a.txt"
    p.write_text("hello", encoding="utf-8")
    edits = json.dumps([{"old_string": "nope", "new_string": "x"}])

    result = await _auto_approve(
        FileEditTool()._arun(file_path=str(p), edits=edits)
    )
    data = _success_data(result)

    assert data["failed_count"] == 1
    assert data["results"][0]["status"] == "error"


# ── file_search_text（保持同步） ───────────────────────────


def test_file_search_text(whitelist_tmp: Path) -> None:
    p = whitelist_tmp / "a.txt"
    p.write_text("line1 alpha\nline2 beta\nalpha again", encoding="utf-8")

    result = FileSearchTextTool()._run(file_path=str(p), pattern="alpha")
    data = _success_data(result)

    assert data["total_matches"] == 2


def test_file_search_text_bad_regex(whitelist_tmp: Path) -> None:
    p = whitelist_tmp / "a.txt"
    p.write_text("hello", encoding="utf-8")

    result = FileSearchTextTool()._run(file_path=str(p), pattern="[unclosed")
    assert "正则表达式错误" in _error_msg(result)


# ── 注册表断言 ─────────────────────────────────────────────


def test_registry_has_all_file_tools_no_manage() -> None:
    names = {t.name for t in get_all_tools()}
    expected = {
        "file_read", "file_write", "file_delete", "file_rename",
        "file_create_directory", "file_list_directory", "file_search",
        "file_edit", "file_search_text",
    }
    assert expected.issubset(names)
    assert "file_manage" not in names
