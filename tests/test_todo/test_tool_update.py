"""todo_update 工具测试。"""

from unittest.mock import MagicMock, PropertyMock

from tools.todo.tool_update import TodoUpdateTool


def _make_tool(mock_api, mock_client):
    tool = TodoUpdateTool(client=mock_client)
    helper = tool.helper
    type(helper).api = PropertyMock(return_value=mock_api)
    return tool


def _fake_task(overrides=None):
    """Create a fake task with sensible defaults."""
    t = MagicMock()
    t.id = "task1"
    t.content = "Old content"
    t.description = "Old desc"
    t.project_id = "proj1"
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
    if overrides:
        for k, v in overrides.items():
            setattr(t, k, v)
    return t


class TestValidation:
    def test_empty_task_id_returns_error(self, mock_api, mock_client):
        tool = _make_tool(mock_api, mock_client)
        result = tool._run(get_doc=False, task_id="")
        assert "不能为空" in result

    def test_invalid_priority_returns_error(self, mock_api, mock_client):
        tool = _make_tool(mock_api, mock_client)
        result = tool._run(get_doc=False, task_id="t1", priority=5)
        assert "无效" in result


class TestUpdateFields:
    def test_update_content_only(self, mock_api, mock_client):
        mock_api.get_task.return_value = _fake_task()
        mock_api.update_task.return_value = _fake_task({"content": "New content"})
        p = type("FakeProject", (), {"id": "proj1", "name": "Work"})()
        mock_api.get_projects.return_value = [[p]]
        mock_api.get_sections.return_value = [[]]

        tool = _make_tool(mock_api, mock_client)
        result = tool._run(get_doc=False, task_id="task1", content="New content")
        assert "success" in result
        mock_api.update_task.assert_called_once()
        assert mock_api.update_task.call_args[1]["content"] == "New content"

    def test_update_description(self, mock_api, mock_client):
        mock_api.get_task.return_value = _fake_task()
        mock_api.update_task.return_value = _fake_task({"description": "New desc"})
        p = type("FakeProject", (), {"id": "proj1", "name": "Work"})()
        mock_api.get_projects.return_value = [[p]]
        mock_api.get_sections.return_value = [[]]

        tool = _make_tool(mock_api, mock_client)
        result = tool._run(get_doc=False, task_id="task1", description="New desc")
        assert "success" in result
        assert mock_api.update_task.call_args[1]["description"] == "New desc"

    def test_update_labels(self, mock_api, mock_client):
        mock_api.get_task.return_value = _fake_task()
        mock_api.update_task.return_value = _fake_task({"labels": ["urgent"]})
        p = type("FakeProject", (), {"id": "proj1", "name": "Work"})()
        mock_api.get_projects.return_value = [[p]]
        mock_api.get_sections.return_value = [[]]

        tool = _make_tool(mock_api, mock_client)
        tool._run(get_doc=False, task_id="task1", labels=["urgent"])
        assert mock_api.update_task.call_args[1]["labels"] == ["urgent"]

    def test_update_due_string(self, mock_api, mock_client):
        mock_api.get_task.return_value = _fake_task()
        mock_api.update_task.return_value = _fake_task()
        p = type("FakeProject", (), {"id": "proj1", "name": "Work"})()
        mock_api.get_projects.return_value = [[p]]
        mock_api.get_sections.return_value = [[]]

        tool = _make_tool(mock_api, mock_client)
        tool._run(get_doc=False, task_id="task1", due_string="next Friday")
        assert mock_api.update_task.call_args[1]["due_string"] == "next Friday"


class TestMoveTask:
    def test_move_project(self, mock_api, mock_client):
        current = _fake_task()
        mock_api.get_task.return_value = current
        mock_api.update_task.return_value = current
        p1 = type("FakeProject", (), {"id": "proj1", "name": "Work"})()
        p2 = type("FakeProject", (), {"id": "proj2", "name": "Personal"})()
        mock_api.get_projects.return_value = [[p1, p2]]
        mock_api.get_sections.return_value = [[]]

        tool = _make_tool(mock_api, mock_client)
        tool._run(get_doc=False, task_id="task1", project_name="Personal")
        mock_api.move_task.assert_called_once_with(task_id="task1", project_id="proj2")

    def test_move_section_within_project(self, mock_api, mock_client):
        current = _fake_task({"project_id": "proj1", "section_id": None})
        mock_api.get_task.return_value = current
        mock_api.update_task.return_value = current
        p1 = type("FakeProject", (), {"id": "proj1", "name": "Work"})()
        s1 = type("FakeSection", (), {"id": "sec1", "name": "Backlog", "project_id": "proj1"})()
        mock_api.get_projects.return_value = [[p1]]
        mock_api.get_sections.return_value = [[s1]]

        tool = _make_tool(mock_api, mock_client)
        tool._run(get_doc=False, task_id="task1", section_name="Backlog")
        mock_api.move_task.assert_called_once_with(task_id="task1", section_id="sec1")

    def test_no_move_when_same_project(self, mock_api, mock_client):
        current = _fake_task({"project_id": "proj1"})
        mock_api.get_task.return_value = current
        mock_api.update_task.return_value = current
        p1 = type("FakeProject", (), {"id": "proj1", "name": "Work"})()
        mock_api.get_projects.return_value = [[p1]]
        mock_api.get_sections.return_value = [[]]

        tool = _make_tool(mock_api, mock_client)
        tool._run(get_doc=False, task_id="task1", project_name="Work")
        mock_api.move_task.assert_not_called()
