"""todo_query 工具测试。"""

from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from tests.test_todo.helpers import apaginate
from tools.todo.tool_query import TodoQueryTool


def _make_tool(mock_api, mock_client):
    tool = TodoQueryTool(client=mock_client)
    helper = tool.helper
    type(helper).api = PropertyMock(return_value=mock_api)
    return tool


class TestQuery:
    @pytest.mark.asyncio
    async def test_empty_task_id_returns_error(self, mock_api, mock_client):
        tool = _make_tool(mock_api, mock_client)
        result = await tool._arun(get_doc=False, task_id="")
        assert "不能为空" in result

    @pytest.mark.asyncio
    async def test_nonexistent_task_returns_error(self, mock_api, mock_client):
        mock_api.get_task = AsyncMock(side_effect=Exception("not found"))
        tool = _make_tool(mock_api, mock_client)
        result = await tool._arun(get_doc=False, task_id="nope")
        assert "不存在" in result

    @pytest.mark.asyncio
    async def test_successful_query_returns_dict(self, mock_api, mock_client):
        t = MagicMock()
        t.id = "t1"
        t.content = "Task"
        t.description = "Desc"
        t.project_id = "p1"
        t.section_id = None
        t.parent_id = None
        t.labels = []
        t.priority = 1
        t.due = None
        t.deadline = None
        t.duration = None
        t.order = 1
        t.is_collapsed = False
        t.assignee_id = None
        t.assigner_id = None
        t.creator_id = "u1"
        t.is_completed = False
        t.url = None
        mock_api.get_task = AsyncMock(return_value=t)
        p = type("FakeProject", (), {"id": "p1", "name": "Work"})()
        mock_api.get_projects = apaginate([[p]])
        mock_api.get_sections = apaginate([[]])

        tool = _make_tool(mock_api, mock_client)
        result = await tool._arun(get_doc=False, task_id="t1")
        assert "success" in result
        assert "task_id" in result
