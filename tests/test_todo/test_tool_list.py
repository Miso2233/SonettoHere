"""todo_list 工具测试 — 过滤参数 + 增强回显。"""

from unittest.mock import MagicMock, PropertyMock

from tools.todo.tool_list import TodoListTool


def _make_tool(mock_api, mock_client):
    tool = TodoListTool(client=mock_client)
    helper = tool.helper
    type(helper).api = PropertyMock(return_value=mock_api)
    return tool


def _fake_task(tid="t1", project_id="proj1", **kw):
    t = MagicMock()
    t.id = tid
    t.content = "Task"
    t.description = ""
    t.project_id = project_id
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
    for k, v in kw.items():
        setattr(t, k, v)
    return t


class TestFilters:
    def test_no_filter_returns_all(self, mock_api, mock_client):
        mock_api.get_tasks.return_value = [[_fake_task(), _fake_task("t2")]]
        p = type("FakeProject", (), {"id": "proj1", "name": "Work"})()
        mock_api.get_projects.return_value = [[p]]
        mock_api.get_sections.return_value = [[]]

        tool = _make_tool(mock_api, mock_client)
        result = tool._run(get_doc=False)
        assert "success" in result
        mock_api.get_tasks.assert_called_once_with()

    def test_filter_by_project_name(self, mock_api, mock_client):
        mock_api.get_tasks.return_value = [[_fake_task()]]
        p = type("FakeProject", (), {"id": "proj1", "name": "Work"})()
        mock_api.get_projects.return_value = [[p]]

        tool = _make_tool(mock_api, mock_client)
        tool._run(get_doc=False, project_name="Work")
        mock_api.get_tasks.assert_called_once_with(project_id="proj1")

    def test_filter_by_label(self, mock_api, mock_client):
        mock_api.get_tasks.return_value = [[]]
        tool = _make_tool(mock_api, mock_client)
        tool._run(get_doc=False, label="urgent")
        mock_api.get_tasks.assert_called_once_with(label="urgent")

    def test_filter_by_parent_id(self, mock_api, mock_client):
        mock_api.get_tasks.return_value = [[]]
        tool = _make_tool(mock_api, mock_client)
        tool._run(get_doc=False, parent_id="parent1")
        mock_api.get_tasks.assert_called_once_with(parent_id="parent1")

    def test_filter_by_ids(self, mock_api, mock_client):
        mock_api.get_tasks.return_value = [[]]
        tool = _make_tool(mock_api, mock_client)
        tool._run(get_doc=False, ids=["t1", "t2"])
        mock_api.get_tasks.assert_called_once_with(ids=["t1", "t2"])

    def test_filter_by_limit(self, mock_api, mock_client):
        mock_api.get_tasks.return_value = [[]]
        tool = _make_tool(mock_api, mock_client)
        tool._run(get_doc=False, limit=50)
        mock_api.get_tasks.assert_called_once_with(limit=50)

    def test_nonexistent_project_returns_empty(self, mock_api, mock_client):
        mock_api.get_projects.return_value = [[]]
        tool = _make_tool(mock_api, mock_client)
        result = tool._run(get_doc=False, project_name="Nope")
        assert '"total": 0' in result
