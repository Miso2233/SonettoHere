"""列表入参容错（``coerce_list_arg`` / ``coerce_tool_args``）行为测试。

背景：部分模型 / 调用链会把数组参数以文本形式下发（``'["a", "b"]'``、
``"['a', 'b']"``），``list[...]`` 字段会在 Pydantic 校验阶段直接报
"Input should be a valid list"，工具还没执行就失败。

验证契约：
- ``coerce_list_arg`` 能还原 JSON 数组文本与 Python 列表 / 元组字面量文本；
  ``wrap_scalar`` 包单个值、``wrap_mapping`` 包单个对象，还原不了时原样返回；
- ``coerce_tool_args`` 按 args_schema 注解自动判断哪些字段是 ``list[...]``，
  元素是模型 / 映射时按单对象包装，否则按单值包装；无变化时不做拷贝；
- 容错挂在 ``ToolBase._parse_input`` 一处 —— 这是 langchain 唯一的入参校验入口，
  故所有原生工具（含 ``@get_doc`` 等装饰器重建过 schema 的工具）自动生效；
- 无法还原的值仍由 pydantic 报错，校验不被放宽。
"""

import json

import pytest
from pydantic import BaseModel, ValidationError

from tools.base import coerce_list_arg, coerce_tool_args
from tools.files.tool_file_edit import FileEditInput, FileEditTool
from tools.interaction.tool_multi_choice import AskUserMultiChoiceTool
from tools.interaction.tool_single_choice import AskUserSingleChoiceTool
from tools.network.tavily.tool_extract import TavilyExtractTool
from tools.network.tavily.tool_search import TavilySearchTool
from tools.task.tool_tracker import TaskTrackerInput, TaskTrackerTool
from tools.todo.tool_add import TodoAddTool
from tools.todo.tool_list import TodoListInput, TodoListTool
from tools.todo.tool_update import TodoUpdateTool

# ── coerce_list_arg 纯函数 ─────────────────────────────────


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ('["a", "b"]', ["a", "b"]),  # JSON 数组文本
        ("['a', 'b']", ["a", "b"]),  # Python 列表字面量
        ("('a', 'b')", ["a", "b"]),  # Python 元组字面量
        ('[{"content": "a"}]', [{"content": "a"}]),
        (["a"], ["a"]),  # 已是列表 → 原样返回
        ("", []),  # 空串 → 空列表
        ("   ", []),
    ],
)
def test_coerce_list_arg_restores_sequence(value: object, expected: list) -> None:
    assert coerce_list_arg(value) == expected


def test_coerce_list_arg_wrap_scalar_wraps_single_value() -> None:
    """单值字段（labels / urls / options）允许直接传一个值。"""
    assert coerce_list_arg("urgent", wrap_scalar=True) == ["urgent"]
    assert coerce_list_arg("https://example.com", wrap_scalar=True) == [
        "https://example.com"
    ]
    assert coerce_list_arg("123", wrap_scalar=True) == [123]


def test_coerce_list_arg_wrap_mapping_wraps_single_object() -> None:
    todo = {"content": "a", "status": "pending"}
    assert coerce_list_arg(todo, wrap_mapping=True) == [todo]
    assert coerce_list_arg(json.dumps(todo), wrap_mapping=True) == [todo]


def test_coerce_list_arg_passthrough_when_uncoercible() -> None:
    """还原不了时保持原值，由 Pydantic 给出准确错误信息。"""
    assert coerce_list_arg("not a list") == "not a list"
    assert coerce_list_arg(None) is None
    assert coerce_list_arg(123) == 123
    assert coerce_list_arg({"a": 1}) == {"a": 1}  # 未开 wrap_mapping 不擅自包装


# ── coerce_tool_args：按注解挑字段与包装语义 ───────────────


def test_coerce_tool_args_wraps_by_item_type() -> None:
    """元素是模型 → 单对象包装；元素是标量 → 单值包装。"""
    todos = {"todos": {"content": "a", "status": "pending"}}
    assert coerce_tool_args(TaskTrackerInput, todos) == {
        "todos": [{"content": "a", "status": "pending"}]
    }
    assert coerce_tool_args(TodoListInput, {"ids": "i1"}) == {"ids": ["i1"]}


def test_coerce_tool_args_leaves_untouched_inputs_alone() -> None:
    """非 dict 入参 / 非模型 schema / 无需还原时都不改写。"""
    assert coerce_tool_args(TodoListInput, "not a dict") == "not a dict"
    assert coerce_tool_args(None, {"ids": "['a']"}) == {"ids": "['a']"}
    assert coerce_tool_args(TodoListInput, {"label": "urgent"}) == {"label": "urgent"}

    payload = {"ids": ["i1"]}  # 已是列表 → 不产生新对象
    assert coerce_tool_args(TodoListInput, payload) is payload


# ── 校验入口：ToolBase._parse_input 一处覆盖全部工具 ───────


def _plain(value: object) -> object:
    """把 pydantic 模型降级成可比较的纯数据（todos 校验后是 TodoItem 列表）。"""
    if isinstance(value, list):
        return [v.model_dump() if isinstance(v, BaseModel) else v for v in value]
    return value


@pytest.mark.parametrize(
    ("tool_factory", "payload", "field", "expected"),
    [
        (
            TaskTrackerTool,
            {"todos": '[{"content": "a", "status": "pending"}]'},
            "todos",
            [{"content": "a", "status": "pending", "activeForm": None}],
        ),
        (
            TaskTrackerTool,
            {"todos": {"content": "a", "status": "pending"}},
            "todos",
            [{"content": "a", "status": "pending", "activeForm": None}],
        ),
        (TodoAddTool, {"labels": '["x", "y"]'}, "labels", ["x", "y"]),
        (TodoAddTool, {"labels": "x"}, "labels", ["x"]),
        (TodoListTool, {"ids": "['i1', 'i2']"}, "ids", ["i1", "i2"]),
        (TodoUpdateTool, {"labels": '["z"]'}, "labels", ["z"]),
        (TavilyExtractTool, {"urls": "https://a.com"}, "urls", ["https://a.com"]),
        (
            TavilyExtractTool,
            {"urls": '["https://a.com"]'},
            "urls",
            ["https://a.com"],
        ),
        (
            TavilySearchTool,
            {"query": "q", "include_domains": '["a.com"]'},
            "include_domains",
            ["a.com"],
        ),
        (
            TavilySearchTool,
            {"query": "q", "exclude_domains": "b.com"},
            "exclude_domains",
            ["b.com"],
        ),
        (AskUserSingleChoiceTool, {"options": "A"}, "options", ["A"]),
        (AskUserMultiChoiceTool, {"options": '["A", "B"]'}, "options", ["A", "B"]),
    ],
)
def test_parse_input_coerces_stringified_list(
    tool_factory: type, payload: dict, field: str, expected: list
) -> None:
    """字符串 / 单值形态的数组入参统一在 _parse_input 处还原。"""
    parsed = tool_factory()._parse_input(payload, None)
    assert _plain(parsed[field]) == expected


def test_parse_input_rejects_uncoercible_value() -> None:
    """容错不放宽校验：还原不了的入参仍由 pydantic 报错。"""
    with pytest.raises(ValidationError):
        TodoListTool()._parse_input({"ids": 12345}, None)


def test_parse_input_leaves_scalar_and_text_fields_alone() -> None:
    """非 list 字段（如 file_edit 的 JSON 文本字段）不被本机制改写。"""
    parsed = TodoListTool()._parse_input({"label": "urgent", "limit": 5}, None)
    assert parsed["label"] == "urgent"
    assert parsed["limit"] == 5


@pytest.mark.asyncio
async def test_task_tracker_end_to_end_accepts_stringified_todos() -> None:
    """端到端：经 BaseTool.arun 完整调用链，字符串化 todos 也能执行成功。"""
    out = await TaskTrackerTool().arun(
        {"todos": '[{"content": "a", "status": "pending"}]'}, tool_call_id="x"
    )
    data = json.loads(getattr(out, "content", out))["data"]

    assert data["total"] == 1
    assert data["pending"] == 1


# ── file_edit：字段是 JSON 文本，方向相反 ───────────────────


def test_file_edit_serializes_parsed_edit_list() -> None:
    raw = [{"old_string": "a", "new_string": "b"}]
    assert json.loads(FileEditInput(edits=raw).edits) == raw


def test_file_edit_serializes_single_edit_object() -> None:
    raw = {"old_string": "a", "new_string": "b"}
    assert json.loads(FileEditInput(edits=raw).edits) == [raw]


def test_file_edit_runtime_accepts_parsed_list(tmp_path) -> None:
    """绕过 args_schema 直接调用 _edit 时，已解析的列表同样可用。"""
    target = tmp_path / "a.txt"
    target.write_text("hello", encoding="utf-8")

    out = json.loads(
        FileEditTool()._edit(str(target), [{"old_string": "hello", "new_string": "hi"}])
    )

    assert out["success"] is True
    assert out["data"]["success_count"] == 1
    assert target.read_text(encoding="utf-8") == "hi"


def test_file_edit_runtime_accepts_json_object_text(tmp_path) -> None:
    """单笔编辑忘了包数组（JSON 对象文本）时也按单笔处理。"""
    target = tmp_path / "b.txt"
    target.write_text("hello", encoding="utf-8")

    out = json.loads(
        FileEditTool()._edit(
            str(target), '{"old_string": "hello", "new_string": "hey"}'
        )
    )

    assert out["success"] is True
    assert target.read_text(encoding="utf-8") == "hey"
