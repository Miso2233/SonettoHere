"""todo_list_sections 工具测试。"""

from unittest.mock import MagicMock, PropertyMock

import pytest

from tests.test_todo.helpers import apaginate
from tools.todo.tool_list_sections import TodoListSectionsTool


def _make_tool(mock_api, mock_client):
    tool = TodoListSectionsTool(client=mock_client)
    helper = tool.helper
    type(helper).api = PropertyMock(return_value=mock_api)
    return tool


class TestListSections:
    @pytest.mark.asyncio
    async def test_list_all_sections(self, mock_api, mock_client):
        s = MagicMock()
        s.id = "s1"
        s.name = "Backlog"
        s.project_id = "p1"
        s.order = 1
        s.is_collapsed = False
        mock_api.get_sections = apaginate([[s]])
        p = type("FakeProject", (), {"id": "p1", "name": "Work"})()
        mock_api.get_projects = apaginate([[p]])

        tool = _make_tool(mock_api, mock_client)
        result = await tool._arun(get_doc=False)
        assert "success" in result

    @pytest.mark.asyncio
    async def test_filter_by_project(self, mock_api, mock_client):
        s = MagicMock()
        s.id = "s1"
        s.name = "Backlog"
        s.project_id = "p1"
        s.order = 1
        s.is_collapsed = False
        mock_api.get_sections = apaginate([[s]])
        p = type("FakeProject", (), {"id": "p1", "name": "Work"})()
        mock_api.get_projects = apaginate([[p]])

        tool = _make_tool(mock_api, mock_client)
        result = await tool._arun(get_doc=False, project_name="Work")
        assert "success" in result

    @pytest.mark.asyncio
    async def test_nonexistent_project_returns_error(self, mock_api, mock_client):
        mock_api.get_projects = apaginate([[]])
        tool = _make_tool(mock_api, mock_client)
        result = await tool._arun(get_doc=False, project_name="Nope")
        assert "不存在" in result
