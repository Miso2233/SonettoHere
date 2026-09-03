"""Tests: 工具输出提取器（api/callbacks/tool_extractors.py）。

当前覆盖 file_edit 提取器的 old_string/new_string 回填（供前端结果气泡渲染 diff）：
- tool_input 为 str(dict)（langchain-core 实际传入格式，需 literal_eval 解析）
- tool_input 为 JSON 字符串（个别路径）
- tool_input 缺失 / 非法 → 优雅降级，results 原样返回
"""

import json

from api.callbacks.tool_extractors import _dispatch


def _make_parsed() -> dict:
    """模拟 file_edit 工具输出（format_success 结构）。"""
    return {
        "success": True,
        "data": {
            "file_path": "C:/tmp/a.py",
            "total_edits": 3,
            "success_count": 2,
            "failed_count": 1,
            "results": [
                {"index": 0, "status": "ok", "replaced_count": 1},
                {"index": 1, "status": "error", "message": "未找到匹配"},
                {"index": 2, "status": "ok", "replaced_count": 3},
            ],
        },
    }


def test_file_edit_backfill_from_str_dict_input() -> None:
    """tool_input 为 str(dict)（单引号）时按 index 回填 old/new。"""
    edits = json.dumps([
        {"old_string": "print(1)", "new_string": "print(2)"},
        {"old_string": "missing", "new_string": "x"},
        {"old_string": "b", "new_string": "", "replace_all": True},
    ])
    # langchain-core 1.x 实际传入格式：str(dict)，嵌套 JSON 串外层为单引号
    tool_input = f"{{'file_path': 'C:/tmp/a.py', 'edits': {edits!r}}}"
    out = _dispatch("file_edit", _make_parsed(), tool_input)

    assert out is not None
    assert out["operation"] == "edit"
    assert out["results"][0]["old_string"] == "print(1)"
    assert out["results"][0]["new_string"] == "print(2)"
    assert out["results"][1]["old_string"] == "missing"
    assert out["results"][2]["new_string"] == ""


def test_file_edit_backfill_from_json_input() -> None:
    """tool_input 为 JSON 字符串时同样回填。"""
    tool_input = json.dumps({
        "file_path": "C:/tmp/a.py",
        "edits": json.dumps([{"old_string": "a", "new_string": "b"}]),
    })
    out = _dispatch("file_edit", _make_parsed(), tool_input)

    assert out is not None
    assert out["results"][0]["old_string"] == "a"
    assert out["results"][0]["new_string"] == "b"


def test_file_edit_backfill_with_quotes_in_edits() -> None:
    """edits 内容含单引号/双引号时 str(dict) 解析不炸、回填不失真。"""
    edits = json.dumps([{"old_string": "it's \"a\"", "new_string": 'b"c'}])
    tool_input = f"{{'edits': {edits!r}}}"
    out = _dispatch("file_edit", _make_parsed(), tool_input)

    assert out is not None
    assert out["results"][0]["old_string"] == "it's \"a\""
    assert out["results"][0]["new_string"] == 'b"c'


def test_file_edit_backfill_edits_as_list() -> None:
    """edits 直接是数组（非 JSON 串）时也能回填（防御）。"""
    tool_input = repr({"file_path": "C:/tmp/a.py", "edits": [{"old_string": "a", "new_string": "b"}]})
    out = _dispatch("file_edit", _make_parsed(), tool_input)

    assert out is not None
    assert out["results"][0]["old_string"] == "a"


def test_file_edit_degrades_without_tool_input() -> None:
    """tool_input 缺失或非法时不回填、不报错，results 原样返回。"""
    parsed = _make_parsed()
    for tool_input in (None, "", "{bad json", "['not', 'a', 'dict']"):
        out = _dispatch("file_edit", parsed, tool_input)
        assert out is not None
        assert out["results"] == parsed["data"]["results"]
        assert "old_string" not in out["results"][0]


def test_file_edit_degrades_on_error_output() -> None:
    """success=false 的输出不提取（与既有提取器行为一致）。"""
    parsed = {"success": False, "error": "文件不存在"}
    assert _dispatch("file_edit", parsed, "{'edits': '[]'}") is None
