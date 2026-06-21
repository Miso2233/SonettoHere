"""todo_add 工具测试。"""

from unittest.mock import MagicMock, PropertyMock

from tools.todo.tool_add import TodoAddTool


def _make_tool(mock_api, mock_client):
    """Helper: create TodoAddTool with mocked api."""
    tool = TodoAddTool(client=mock_client)
    helper = tool.helper
    type(helper).api = PropertyMock(return_value=mock_api)
    return tool


class TestValidation:
    def test_get_doc_returns_doc(self, mock_client):
        """get_doc=True → 不调 API，返回文档。"""
        tool = TodoAddTool(client=mock_client)
        result = tool._run(get_doc=True)
        assert "本 Tool 暂无文档" in result or "Todoist" in result

    def test_empty_content_returns_error(self, mock_client):
        tool = TodoAddTool(client=mock_client)
        result = tool._run(get_doc=False, content="")
        assert "不能为空" in result

    def test_invalid_priority_returns_error(self, mock_client):
        tool = TodoAddTool(client=mock_client)
        result = tool._run(get_doc=False, content="test", priority=5)
        assert "无效" in result


class TestCreateTask:
    def test_basic_create(self, mock_api, mock_client):
        """最基本创建：仅传 content。"""
        mock_task = MagicMock()
        mock_task.id = "new123"
        mock_task.content = "Hello"
        mock_task.description = ""
        mock_task.project_id = "inbox_id"
        mock_task.section_id = None
        mock_task.parent_id = None
        mock_task.labels = []
        mock_task.priority = 1
        mock_task.due = None
        mock_task.deadline = None
        mock_task.duration = None
        mock_task.order = 1
        mock_task.is_collapsed = False
        mock_task.assignee_id = None
        mock_task.assigner_id = None
        mock_task.creator_id = "u1"
        mock_task.is_completed = False
        mock_task.url = None
        mock_api.add_task.return_value = mock_task

        # Mock project + section lookups
        p = type("FakeProject", (), {"id": "inbox_id", "name": "Inbox"})()
        mock_api.get_projects.return_value = [[p]]
        mock_api.get_sections.return_value = [[]]

        tool = _make_tool(mock_api, mock_client)
        result = tool._run(get_doc=False, content="Hello")

        assert '"success": true' in result or "success" in result
        mock_api.add_task.assert_called_once()
        kwargs = mock_api.add_task.call_args[1]
        assert kwargs["content"] == "Hello"

    def test_create_with_all_basic_fields(self, mock_api, mock_client):
        """创建时传所有基本字段。"""
        mock_task = MagicMock()
        mock_task.id = "new456"
        mock_task.content = "Test task"
        mock_task.description = "A description"
        mock_task.project_id = "proj123"
        mock_task.section_id = "sec789"
        mock_task.parent_id = None
        mock_task.labels = ["urgent"]
        mock_task.priority = 3
        mock_task.due = None
        mock_task.deadline = None
        mock_task.duration = None
        mock_task.order = 1
        mock_task.is_collapsed = False
        mock_task.assignee_id = "user2"
        mock_task.assigner_id = None
        mock_task.creator_id = "u1"
        mock_task.is_completed = False
        mock_task.url = None
        mock_api.add_task.return_value = mock_task

        p1 = type("FakeProject", (), {"id": "proj123", "name": "My Project"})()
        s1 = type("FakeSection", (), {"id": "sec789", "name": "Backlog", "project_id": "proj123"})()
        mock_api.get_projects.return_value = [[p1]]
        mock_api.get_sections.return_value = [[s1]]

        tool = _make_tool(mock_api, mock_client)
        result = tool._run(
            get_doc=False,
            content="Test task",
            description="A description",
            due_string="next Monday",
            due_lang="en",
            priority=3,
            project_name="My Project",
            section_name="Backlog",
            labels=["urgent"],
            parent_id=None,
            assignee_id="user2",
            order=5,
        )

        assert "success" in result
        kwargs = mock_api.add_task.call_args[1]
        assert kwargs["content"] == "Test task"
        assert kwargs["description"] == "A description"
        assert kwargs["due_string"] == "next Monday"
        assert kwargs["due_lang"] == "en"
        assert kwargs["priority"] == 3
        assert kwargs["labels"] == ["urgent"]
        assert kwargs["assignee_id"] == "user2"
        assert kwargs["order"] == 5

    def test_create_with_due_date(self, mock_api, mock_client):
        """due_date 被正确解析为 date 对象。"""
        mock_task = MagicMock()
        mock_task.id = "t1"
        mock_api.add_task.return_value = mock_task
        p = type("FakeProject", (), {"id": "p1", "name": "Inbox"})()
        mock_api.get_projects.return_value = [[p]]
        mock_api.get_sections.return_value = [[]]

        tool = _make_tool(mock_api, mock_client)
        tool._run(get_doc=False, content="Test", due_date="2026-07-15")

        kwargs = mock_api.add_task.call_args[1]
        from datetime import date
        assert kwargs["due_date"] == date(2026, 7, 15)

    def test_create_with_labels(self, mock_api, mock_client):
        """labels 列表被正确传递。"""
        mock_task = MagicMock()
        mock_task.id = "t1"
        mock_api.add_task.return_value = mock_task
        p = type("FakeProject", (), {"id": "p1", "name": "Inbox"})()
        mock_api.get_projects.return_value = [[p]]
        mock_api.get_sections.return_value = [[]]

        tool = _make_tool(mock_api, mock_client)
        tool._run(get_doc=False, content="Test", labels=["urgent", "work"])

        kwargs = mock_api.add_task.call_args[1]
        assert kwargs["labels"] == ["urgent", "work"]

    def test_create_with_duration(self, mock_api, mock_client):
        """duration / duration_unit 被传入。"""
        mock_task = MagicMock()
        mock_task.id = "t1"
        mock_api.add_task.return_value = mock_task
        p = type("FakeProject", (), {"id": "p1", "name": "Inbox"})()
        mock_api.get_projects.return_value = [[p]]
        mock_api.get_sections.return_value = [[]]

        tool = _make_tool(mock_api, mock_client)
        tool._run(get_doc=False, content="Test", duration=30, duration_unit="minute")

        kwargs = mock_api.add_task.call_args[1]
        assert kwargs["duration"] == 30
        assert kwargs["duration_unit"] == "minute"

    def test_create_with_deadline(self, mock_api, mock_client):
        """deadline_date 被解析为 date 对象。"""
        mock_task = MagicMock()
        mock_task.id = "t1"
        mock_api.add_task.return_value = mock_task
        p = type("FakeProject", (), {"id": "p1", "name": "Inbox"})()
        mock_api.get_projects.return_value = [[p]]
        mock_api.get_sections.return_value = [[]]

        tool = _make_tool(mock_api, mock_client)
        tool._run(get_doc=False, content="Test", deadline_date="2026-08-01")

        from datetime import date
        kwargs = mock_api.add_task.call_args[1]
        assert kwargs["deadline_date"] == date(2026, 8, 1)

    def test_nonexistent_project_returns_error(self, mock_api, mock_client):
        mock_api.get_projects.return_value = [[]]
        tool = _make_tool(mock_api, mock_client)
        result = tool._run(get_doc=False, content="Test", project_name="Nope")
        assert "不存在" in result

    def test_nonexistent_section_returns_error(self, mock_api, mock_client):
        p = type("FakeProject", (), {"id": "p1", "name": "MyProject"})()
        mock_api.get_projects.return_value = [[p]]
        mock_api.get_sections.return_value = [[]]
        tool = _make_tool(mock_api, mock_client)
        result = tool._run(get_doc=False, content="Test", project_name="MyProject", section_name="Nope")
        assert "不存在" in result
