"""@get_doc 类装饰器（tools/get_doc.py）行为测试。

验证核心契约：
- 类装饰器把 get_doc 作为「非必填、默认 False」字段注入 args_schema，
  模型侧 schema（JSON Schema / Input pydantic 模型）即可见该参数；
- ``get_doc=True`` 时短路返回 ``self._load_doc()``（TOOL.md 目录文档），
  不触达真实业务逻辑、无副作用；
- ``get_doc=False`` / 缺省时原样转发到真正执行的方法（sync 的 ``_run`` /
  async 的 ``_arun``），既有行为不变；
- 纯 Command 工具（read_image）也能普通返回文档字符串，无需再包 ToolMessage；
- 无参装饰器：所有工具的 get_doc 字段统一用默认文案（不再提供 per-tool 覆写，
  更长引导文案交由同目录 TOOL.md 承载）。

代表工具：TodoAddTool（已异步化，包装 ``_arun``）与 CallSubAgentTool
（包装 ``_arun``），Command 用 ReadImageTool（本阶段特例）。
"""

import pytest

from tools.network.tool_read_image import ReadImageTool
from tools.sub_agent.tool_call_sub_agent import CallSubAgentTool
from tools.todo.tool_add import TodoAddTool

_DEFAULT_DESC = "设为 true 以获取使用说明"


# ── schema 注入 ────────────────────────────────────────────


def test_sync_tool_injects_get_doc_non_required() -> None:
    """args_schema 出现非必填 get_doc;原字段仍在（未被装饰过程覆盖丢失）。"""
    fields = TodoAddTool().get_input_schema().model_fields
    assert "get_doc" in fields
    assert fields["get_doc"].is_required() is False
    assert fields["get_doc"].default is False
    assert "content" in fields  # 原字段保留


def test_async_tool_injects_get_doc_non_required() -> None:
    """async 工具（包装 _arun）同样注入 schema。"""
    fields = CallSubAgentTool().get_input_schema().model_fields
    assert "get_doc" in fields
    assert fields["get_doc"].is_required() is False
    assert "task" in fields


def test_decorator_uses_default_description() -> None:
    """@get_doc 不再接受参数，各工具 get_doc 字段统一为默认文案。"""
    for tool in (TodoAddTool(), ReadImageTool()):
        prop = tool.get_input_schema().model_json_schema()["properties"]["get_doc"]
        assert prop["default"] is False
        assert prop["description"] == _DEFAULT_DESC


# ── async 行为（包装 _arun，TodoAddTool 已异步化）─────────


@pytest.mark.asyncio
async def test_todo_add_get_doc_short_circuits() -> None:
    """get_doc=True → 返回 _load_doc() 文档，不触达业务逻辑。"""
    tool = TodoAddTool()
    result = await tool._arun(get_doc=True)
    assert result == tool._load_doc()
    assert "Todoist" in result or "本 Tool 暂无文档" in result


@pytest.mark.asyncio
async def test_todo_add_get_doc_false_forwards_to_logic() -> None:
    """get_doc=False → 原样转发，校验逻辑照常执行。"""
    tool = TodoAddTool()
    result = await tool._arun(get_doc=False, content="")
    assert "不能为空" in result


@pytest.mark.asyncio
async def test_todo_add_without_get_doc_forwards_to_logic() -> None:
    """不传 get_doc（缺省 False）→ 同样转发。"""
    tool = TodoAddTool()
    result = await tool._arun(content="")
    assert "不能为空" in result


# ── async 行为（包装 _arun）──────────────────────────────


@pytest.mark.asyncio
async def test_async_get_doc_short_circuits() -> None:
    """async 工具 get_doc=True → 返回 _load_doc() 文档。"""
    tool = CallSubAgentTool()
    result = await tool._arun(get_doc=True)
    assert result == tool._load_doc()


@pytest.mark.asyncio
async def test_async_get_doc_false_forwards_to_logic() -> None:
    """async 工具 get_doc=False → 原样转发到真实 _arun 校验逻辑。"""
    tool = CallSubAgentTool()
    result = await tool._arun(get_doc=False, task="")
    assert "不能为空" in result


# ── read_image 特例（Command 工具普通返回文档）────────────


@pytest.mark.asyncio
async def test_read_image_get_doc_returns_plain_string() -> None:
    """get_doc 走普通字符串返回（不再包 Command/ToolMessage）。"""
    tool = ReadImageTool()
    result = await tool._arun(get_doc=True)
    assert isinstance(result, str)
    assert result == tool._load_doc()


@pytest.mark.asyncio
async def test_read_image_normal_path_still_returns_command() -> None:
    """正常路径（get_doc=False）仍返回 Command 注入消息流，未受影响。"""
    from langgraph.types import Command

    tool = ReadImageTool()
    result = await tool._arun(image_path="")
    assert isinstance(result, Command)
    assert "不能为空" in result.update["messages"][0].content  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_read_image_langchain_roundtrip_doc() -> None:
    """端到端：经 BaseTool.arun（带 tool_call_id 的完整调用）执行，
    get_doc 短路返回普通文档——不再包 Command；langchain 将该字符串归一为
    ToolMessage，其 content 即 TOOL.md 文档文本。"""
    from langchain_core.messages import ToolMessage

    tool = ReadImageTool()
    out = await tool.arun({"get_doc": True}, tool_call_id="x")
    assert isinstance(out, ToolMessage)
    assert out.content == ReadImageTool()._load_doc()
