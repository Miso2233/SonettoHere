"""todo_list_sections 工具测试。"""

from unittest.mock import MagicMock, PropertyMock

from tools.todo.tool_list_sections import TodoListSectionsTool


def _make_tool(mock_api, mock_client):
    tool = TodoListSectionsTool(client=mock_client)
    helper = tool.helper
    type(helper).api = PropertyMock(return_value=mock_api)
    return tool


class TestListSections:
    def test_list_all_sections(self, mock_api, mock_client):
        s = MagicMock()
        s.id = "s1"
        s.name = "Backlog"
        s.project_id = "p1"
        s.order = 1
        s.is_collapsed = False
        mock_api.get_sections.return_value = [[s]]
        p = type("FakeProject", (), {"id": "p1", "name": "Work"})()
        mock_api.get_projects.return_value = [[p]]

        tool = _make_tool(mock_api, mock_client)
        result = tool._run(get_doc=False)
        assert "success" in result

    def test_filter_by_project(self, mock_api, mock_client):
        s = MagicMock()
        s.id = "s1"
        s.name = "Backlog"
        s.project_id = "p1"
        s.order = 1
        s.is_collapsed = False
        mock_api.get_sections.return_value = [[s]]
        p = type("FakeProject", (), {"id": "p1", "name": "Work"})()
        mock_api.get_projects.return_value = [[p]]

        tool = _make_tool(mock_api, mock_client)
        result = tool._run(get_doc=False, project_name="Work")
        assert "success" in result

    def test_nonexistent_project_returns_error(self, mock_api, mock_client):
        mock_api.get_projects.return_value = [[]]
        tool = _make_tool(mock_api, mock_client)
        result = tool._run(get_doc=False, project_name="Nope")
        assert "不存在" in result
