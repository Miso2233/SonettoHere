"""todo_list_projects 工具测试。"""

from unittest.mock import MagicMock, PropertyMock

from tools.todo.tool_list_projects import TodoListProjectsTool


def _make_tool(mock_api, mock_client):
    tool = TodoListProjectsTool(client=mock_client)
    helper = tool.helper
    type(helper).api = PropertyMock(return_value=mock_api)
    return tool


class TestListProjects:
    def test_returns_all_fields(self, mock_api, mock_client):
        p = MagicMock()
        p.id = "p1"
        p.name = "Work"
        p.description = "Work tasks"
        p.color = "blue"
        p.order = 1
        p.is_favorite = True
        p.is_archived = False
        p.is_shared = False
        p.is_collapsed = False
        p.parent_id = None
        p.view_style = "list"
        p.can_assign_tasks = True
        p.is_inbox_project = False
        p.workspace_id = "ws1"
        p.folder_id = None
        mock_api.get_projects.return_value = [[p]]

        tool = _make_tool(mock_api, mock_client)
        result = tool._run(get_doc=False)

        assert "success" in result
        assert "project_id" in result
        assert "description" in result
        assert "color" in result
        assert "is_favorite" in result
