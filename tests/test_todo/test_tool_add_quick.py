"""todo_add_quick 工具测试。"""

from unittest.mock import MagicMock, PropertyMock

from tools.todo.tool_add_quick import TodoAddQuickTool


def _make_tool(mock_api, mock_client):
    tool = TodoAddQuickTool(client=mock_client)
    helper = tool.helper
    type(helper).api = PropertyMock(return_value=mock_api)
    return tool


class TestAddQuick:
    def test_empty_text_returns_error(self, mock_api, mock_client):
        tool = _make_tool(mock_api, mock_client)
        result = tool._run(get_doc=False, text="")
        assert "不能为空" in result

    def test_add_quick_with_text_only(self, mock_api, mock_client):
        t = MagicMock()
        t.id = "new1"
        t.content = "Buy milk"
        t.description = ""
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
        mock_api.add_task_quick.return_value = t
        p = type("FakeProject", (), {"id": "p1", "name": "Inbox"})()
        mock_api.get_projects.return_value = [[p]]
        mock_api.get_sections.return_value = [[]]

        tool = _make_tool(mock_api, mock_client)
        result = tool._run(get_doc=False, text="Buy milk")
        assert "success" in result
        mock_api.add_task_quick.assert_called_once_with(
            text="Buy milk", note=None, reminder=None, auto_reminder=True
        )

    def test_add_quick_with_note(self, mock_api, mock_client):
        t = MagicMock()
        t.id = "new1"
        t.content = "Task"
        t.project_id = "p1"
        t.section_id = None
        t.description = ""
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
        mock_api.add_task_quick.return_value = t
        p = type("FakeProject", (), {"id": "p1", "name": "Inbox"})()
        mock_api.get_projects.return_value = [[p]]
        mock_api.get_sections.return_value = [[]]

        tool = _make_tool(mock_api, mock_client)
        tool._run(get_doc=False, text="Task", note="A note")
        mock_api.add_task_quick.assert_called_once_with(
            text="Task", note="A note", reminder=None, auto_reminder=True
        )
