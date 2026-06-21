"""Todo 工具测试 — 共享 fixtures。"""

from unittest.mock import MagicMock, PropertyMock

import pytest

from tools.base import SharedAPIClient
from tools.todo.todo_base import TodoAPIHelper


@pytest.fixture
def mock_api():
    """Mocked TodoistAPI instance."""
    return MagicMock()


@pytest.fixture
def mock_client():
    """Mocked SharedAPIClient with fake todoist token."""
    client = MagicMock(spec=SharedAPIClient)
    client._todoist_token = "fake-token"
    return client


@pytest.fixture
def helper(mock_api):
    """TodoAPIHelper with mocked api property."""
    h = TodoAPIHelper("fake-token")
    type(h).api = PropertyMock(return_value=mock_api)
    return h


@pytest.fixture
def mock_project():
    """Standard mock Project object."""
    p = MagicMock()
    p.id = "proj123"
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
    return p


@pytest.fixture
def mock_section():
    """Standard mock Section object."""
    s = MagicMock()
    s.id = "sec789"
    s.name = "Backlog"
    s.project_id = "proj123"
    s.order = 1
    s.is_collapsed = False
    return s


@pytest.fixture
def mock_label():
    """Standard mock Label object."""
    l = MagicMock()
    l.id = "lab456"
    l.name = "urgent"
    l.color = "red"
    l.order = 1
    l.is_favorite = False
    return l


@pytest.fixture
def mock_task():
    """Standard mock Task object with all fields populated."""
    t = MagicMock()
    t.id = "task999"
    t.content = "Test task"
    t.description = "Test description"
    t.project_id = "proj123"
    t.section_id = "sec789"
    t.parent_id = None
    t.labels = ["urgent", "work"]
    t.priority = 2
    t.order = 1
    t.is_collapsed = False
    t.assignee_id = None
    t.assigner_id = None
    t.creator_id = "user1"
    t.is_completed = False
    t.url = None

    due = MagicMock()
    due.date = "2026-07-01"
    due.string = "next Monday"
    due.lang = "en"
    due.is_recurring = False
    due.timezone = None
    t.due = due

    deadline = MagicMock()
    deadline.date = "2026-07-05"
    deadline.lang = "en"
    t.deadline = deadline

    duration = MagicMock()
    duration.amount = 30
    duration.unit = "minute"
    t.duration = duration

    return t
