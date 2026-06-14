"""Todoist API 共享封装（内部依赖，不是 Tool）。"""

from datetime import datetime
from typing import Optional

from todoist_api_python.api import TodoistAPI


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

    def get_project_id(self, project_name: str) -> str | None:
        for projects in self.api.get_projects():
            for project in projects:
                if project.name.lower() == project_name.lower():
                    return project.id
        return None

    def get_project_name(self, project_id: str) -> str:
        for projects in self.api.get_projects():
            for project in projects:
                if project.id == project_id:
                    return project.name
        return "Inbox"

    @staticmethod
    def parse_date(date_str: str) -> datetime | None:
        formats = ["%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except (ValueError, TypeError):
                continue
        return None

    @staticmethod
    def format_due_date(task) -> str | None:
        if task.due and task.due.date:
            return str(task.due.date)
        return None

    @staticmethod
    def now_str() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
