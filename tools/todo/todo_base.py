"""Todoist API 共享封装（内部依赖，不是 Tool）。"""

from datetime import date, datetime

from todoist_api_python.api import TodoistAPI
from todoist_api_python.models import Label, Project, Section, Task


class TodoAPIHelper:
    """封装 Todoist API 的通用方法，供各 Todo Tool 调用。"""

    def __init__(self, token: str):
        self._api: TodoistAPI | None = None
        self._token = token

    @property
    def api(self) -> TodoistAPI:
        if self._api is None:
            if not self._token:
                raise ValueError("未找到 Todoist API Token")
            self._api = TodoistAPI(self._token)
        return self._api

    # ── 项目 ──

    def get_project_id(self, project_name: str) -> str | None:
        """按名称查找 project ID（大小写不敏感）。"""
        for projects in self.api.get_projects():
            for project in projects:
                if project.name.lower() == project_name.lower():
                    return project.id
        return None

    def get_project_name(self, project_id: str) -> str:
        """按 ID 查找项目名称，未找到返回 'Inbox'。"""
        for projects in self.api.get_projects():
            for project in projects:
                if project.id == project_id:
                    return project.name
        return "Inbox"

    # ── 分区 ──

    def get_section_id(self, section_name: str, project_id: str) -> str | None:
        """按名称和所属项目查找 section ID。"""
        for sections in self.api.get_sections(project_id=project_id):
            for section in sections:
                if section.name.lower() == section_name.lower():
                    return section.id
        return None

    def get_section_name(self, section_id: str, project_id: str | None = None) -> str | None:
        """按 ID 查找 section 名称。传入 project_id 可缩小搜索范围。"""
        for sections in self.api.get_sections(project_id=project_id):
            for section in sections:
                if section.id == section_id:
                    return section.name
        return None

    def find_section_global(self, section_name: str) -> tuple[str, str] | None:
        """在所有项目中查找指定名称的 section，返回 (project_id, section_id)。"""
        for sections in self.api.get_sections():
            for section in sections:
                if section.name.lower() == section_name.lower():
                    return section.project_id, section.id
        return None

    def get_sections_by_project(self, project_name: str) -> list[Section]:
        """按项目名获取所有分区列表。"""
        pid = self.get_project_id(project_name)
        if pid is None:
            return []
        result: list[Section] = []
        for sections in self.api.get_sections(project_id=pid):
            result.extend(sections)
        return result

    def get_all_sections(self) -> list[Section]:
        """获取所有项目的所有分区。"""
        result: list[Section] = []
        for sections in self.api.get_sections():
            result.extend(sections)
        return result

    # ── 标签 ──

    def get_all_labels(self) -> list[Label]:
        """获取所有标签。"""
        result: list[Label] = []
        for labels in self.api.get_labels():
            result.extend(labels)
        return result

    # ── 日期解析 ──

    @staticmethod
    def parse_date(date_str: str) -> datetime | None:
        """解析日期字符串为 datetime（兼容 YYYY-MM-DD / YYYY-MM-DD HH:MM / YYYY-MM-DDTHH:MM）。"""
        formats = ["%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except (ValueError, TypeError):
                continue
        return None

    @staticmethod
    def parse_deadline(date_str: str) -> date | None:
        """解析 deadline 日期字符串为 date 对象（仅 YYYY-MM-DD）。"""
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            return None

    @staticmethod
    def parse_datetime(date_str: str) -> datetime | None:
        """解析含时间的日期字符串为 datetime 对象。"""
        formats = ["%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M", "%Y-%m-%d"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except (ValueError, TypeError):
                continue
        return None

    # ── 格式化（旧接口，保留向后兼容）──

    @staticmethod
    def format_due_date(task) -> str | None:
        """从 task.due 中提取日期字符串。"""
        if task.due and task.due.date:
            return str(task.due.date)
        return None

    @staticmethod
    def now_str() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── 统一序列化 ──

    def task_to_dict(self, task: Task) -> dict:
        """Task → 完整响应字典。供 add / update / query / list / add_quick 统一使用。"""
        due_dict: dict | None = None
        if task.due:
            due_dict = {
                "date": str(task.due.date) if task.due.date else None,
                "string": task.due.string,
                "lang": task.due.lang,
                "is_recurring": task.due.is_recurring,
                "timezone": task.due.timezone,
            }

        deadline_dict: dict | None = None
        if task.deadline:
            deadline_dict = {
                "date": str(task.deadline.date) if task.deadline.date else None,
                "lang": task.deadline.lang,
            }

        duration_dict: dict | None = None
        if task.duration:
            duration_dict = {
                "amount": task.duration.amount,
                "unit": task.duration.unit,
            }

        return {
            "task_id": task.id,
            "content": task.content,
            "description": task.description,
            "project_id": task.project_id,
            "project_name": self.get_project_name(task.project_id),
            "section_id": task.section_id,
            "section_name": (
                self.get_section_name(task.section_id, task.project_id)
                if task.section_id
                else None
            ),
            "parent_id": task.parent_id,
            "labels": task.labels,
            "priority": task.priority,
            "due": due_dict,
            "deadline": deadline_dict,
            "duration": duration_dict,
            "order": task.order,
            "is_collapsed": task.is_collapsed,
            "assignee_id": task.assignee_id,
            "assigner_id": task.assigner_id,
            "creator_id": task.creator_id,
            "is_completed": task.is_completed,
            "url": getattr(task, "url", None),
        }

    def project_to_dict(self, project: Project) -> dict:
        """Project → 响应字典。"""
        return {
            "project_id": project.id,
            "name": project.name,
            "description": project.description,
            "color": project.color,
            "order": project.order,
            "is_favorite": project.is_favorite,
            "is_archived": project.is_archived,
            "is_shared": project.is_shared,
            "is_collapsed": project.is_collapsed,
            "parent_id": project.parent_id,
            "view_style": project.view_style,
            "can_assign_tasks": project.can_assign_tasks,
            "is_inbox_project": project.is_inbox_project,
            "workspace_id": project.workspace_id,
            "folder_id": project.folder_id,
        }

    def section_to_dict(self, section: Section) -> dict:
        """Section → 响应字典。"""
        return {
            "section_id": section.id,
            "name": section.name,
            "project_id": section.project_id,
            "project_name": self.get_project_name(section.project_id),
            "order": section.order,
            "is_collapsed": section.is_collapsed,
        }

    @staticmethod
    def label_to_dict(label: Label) -> dict:
        """Label → 响应字典。"""
        return {
            "label_id": label.id,
            "name": label.name,
            "color": label.color,
            "order": label.order,
            "is_favorite": label.is_favorite,
        }
