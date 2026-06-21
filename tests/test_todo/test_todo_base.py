"""TodoAPIHelper 单元测试。"""

from datetime import date, datetime

from tools.todo.todo_base import TodoAPIHelper


class TestParseDate:
    def test_ymd(self):
        result = TodoAPIHelper.parse_date("2026-07-01")
        assert result == datetime(2026, 7, 1)

    def test_ymd_hms(self):
        result = TodoAPIHelper.parse_date("2026-07-01 15:30")
        assert result == datetime(2026, 7, 1, 15, 30)

    def test_ymd_thms(self):
        result = TodoAPIHelper.parse_date("2026-07-01T15:30")
        assert result == datetime(2026, 7, 1, 15, 30)

    def test_invalid_returns_none(self):
        result = TodoAPIHelper.parse_date("not-a-date")
        assert result is None

    def test_empty_returns_none(self):
        result = TodoAPIHelper.parse_date("")
        assert result is None


class TestParseDeadline:
    def test_valid(self):
        result = TodoAPIHelper.parse_deadline("2026-07-01")
        assert result == date(2026, 7, 1)
        assert isinstance(result, date)

    def test_invalid_returns_none(self):
        result = TodoAPIHelper.parse_deadline("not-a-date")
        assert result is None


class TestParseDatetime:
    def test_ymd_hms(self):
        result = TodoAPIHelper.parse_datetime("2026-07-01 15:30")
        assert result == datetime(2026, 7, 1, 15, 30)

    def test_ymd_thms(self):
        result = TodoAPIHelper.parse_datetime("2026-07-01T15:30")
        assert result == datetime(2026, 7, 1, 15, 30)

    def test_ymd(self):
        """parse_datetime also accepts bare date."""
        result = TodoAPIHelper.parse_datetime("2026-07-01")
        assert result == datetime(2026, 7, 1)

    def test_invalid_returns_none(self):
        result = TodoAPIHelper.parse_datetime("")
        assert result is None


class TestGetProjectId:
    def test_found(self, helper, mock_api):
        p = type("FakeProject", (), {"id": "p1", "name": "Work"})()
        mock_api.get_projects.return_value = [[p]]

        result = helper.get_project_id("Work")
        assert result == "p1"

    def test_case_insensitive(self, helper, mock_api):
        p = type("FakeProject", (), {"id": "p1", "name": "Work"})()
        mock_api.get_projects.return_value = [[p]]

        result = helper.get_project_id("work")
        assert result == "p1"

    def test_not_found(self, helper, mock_api):
        p = type("FakeProject", (), {"id": "p1", "name": "Work"})()
        mock_api.get_projects.return_value = [[p]]

        result = helper.get_project_id("Nope")
        assert result is None


class TestGetProjectName:
    def test_found(self, helper, mock_api):
        p = type("FakeProject", (), {"id": "p1", "name": "Work"})()
        mock_api.get_projects.return_value = [[p]]

        result = helper.get_project_name("p1")
        assert result == "Work"

    def test_not_found_returns_inbox(self, helper, mock_api):
        mock_api.get_projects.return_value = [[]]
        result = helper.get_project_name("nope")
        assert result == "Inbox"


class TestGetSectionId:
    def test_found(self, helper, mock_api):
        s = type("FakeSection", (), {"id": "s1", "name": "Backlog", "project_id": "p1"})()
        mock_api.get_sections.return_value = [[s]]

        result = helper.get_section_id("Backlog", "p1")
        assert result == "s1"

    def test_case_insensitive(self, helper, mock_api):
        s = type("FakeSection", (), {"id": "s1", "name": "Backlog", "project_id": "p1"})()
        mock_api.get_sections.return_value = [[s]]

        result = helper.get_section_id("backlog", "p1")
        assert result == "s1"

    def test_not_found(self, helper, mock_api):
        mock_api.get_sections.return_value = [[]]
        result = helper.get_section_id("Nope", "p1")
        assert result is None


class TestGetSectionName:
    def test_found(self, helper, mock_api):
        s = type("FakeSection", (), {"id": "s1", "name": "Backlog", "project_id": "p1"})()
        mock_api.get_sections.return_value = [[s]]

        result = helper.get_section_name("s1")
        assert result == "Backlog"

    def test_not_found(self, helper, mock_api):
        mock_api.get_sections.return_value = [[]]
        result = helper.get_section_name("nope")
        assert result is None


class TestFindSectionGlobal:
    def test_found(self, helper, mock_api):
        s = type("FakeSection", (), {"id": "s1", "name": "Backlog", "project_id": "p1"})()
        mock_api.get_sections.return_value = [[s]]

        result = helper.find_section_global("Backlog")
        assert result == ("p1", "s1")

    def test_not_found(self, helper, mock_api):
        mock_api.get_sections.return_value = [[]]
        result = helper.find_section_global("Nope")
        assert result is None


class TestGetAllLabels:
    def test_returns_flat_list(self, helper, mock_api):
        l1 = type("FakeLabel", (), {"id": "l1", "name": "urgent", "color": "red",
                                     "order": 1, "is_favorite": False})()
        l2 = type("FakeLabel", (), {"id": "l2", "name": "work", "color": "blue",
                                     "order": 2, "is_favorite": False})()
        mock_api.get_labels.return_value = [[l1], [l2]]

        result = helper.get_all_labels()
        assert len(result) == 2
        assert result[0].name == "urgent"
        assert result[1].name == "work"


class TestTaskToDict:
    def test_all_fields_present(self, helper, mock_task, mock_api):
        mock_api.get_projects.return_value = [
            [type("FakeProject", (), {"id": "proj123", "name": "Work"})()]
        ]
        mock_api.get_sections.return_value = [
            [type("FakeSection", (), {"id": "sec789", "name": "Backlog", "project_id": "proj123"})()]
        ]

        result = helper.task_to_dict(mock_task)

        assert result["task_id"] == "task999"
        assert result["content"] == "Test task"
        assert result["description"] == "Test description"
        assert result["project_id"] == "proj123"
        assert result["project_name"] == "Work"
        assert result["section_id"] == "sec789"
        assert result["section_name"] == "Backlog"
        assert result["parent_id"] is None
        assert result["labels"] == ["urgent", "work"]
        assert result["priority"] == 2
        assert result["order"] == 1
        assert result["is_collapsed"] is False
        assert result["is_completed"] is False

        # Sub-models
        assert result["due"]["date"] == "2026-07-01"
        assert result["due"]["string"] == "next Monday"
        assert result["deadline"]["date"] == "2026-07-05"
        assert result["duration"]["amount"] == 30
        assert result["duration"]["unit"] == "minute"


class TestProjectToDict:
    def test_all_fields_present(self, helper, mock_project):
        result = helper.project_to_dict(mock_project)
        assert result["project_id"] == "proj123"
        assert result["name"] == "Work"
        assert result["description"] == "Work tasks"
        assert result["color"] == "blue"
        assert result["is_favorite"] is True
        assert result["is_archived"] is False
        assert result["view_style"] == "list"


class TestSectionToDict:
    def test_all_fields_present(self, helper, mock_section, mock_api):
        mock_api.get_projects.return_value = [
            [type("FakeProject", (), {"id": "proj123", "name": "Work"})()]
        ]
        result = helper.section_to_dict(mock_section)
        assert result["section_id"] == "sec789"
        assert result["name"] == "Backlog"
        assert result["project_name"] == "Work"


class TestLabelToDict:
    def test_all_fields_present(self, helper, mock_label):
        result = helper.label_to_dict(mock_label)
        assert result["label_id"] == "lab456"
        assert result["name"] == "urgent"
        assert result["color"] == "red"
