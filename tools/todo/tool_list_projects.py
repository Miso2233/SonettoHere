"""Tool: todo_list_projects — 列出所有项目。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success
from tools.todo.todo_base import TodoAPIHelper


class TodoListProjectsInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")


class TodoListProjectsTool(ToolBase):
    name: str = "todo_list_projects"
    description: str = "列出 Todoist 中所有项目及其 ID。添加任务前建议先调用以确认项目名。[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    args_schema: type[BaseModel] = TodoListProjectsInput

    _helper: TodoAPIHelper | None = None

    @property
    def helper(self) -> TodoAPIHelper:
        if self._helper is None:
            self._helper = TodoAPIHelper(self.client._todoist_token)
        return self._helper

    def _run(self, get_doc: bool = False) -> str:
        if get_doc:
            return self._load_doc()

        try:
            api = self.helper.api
        except ValueError as e:
            return format_error(str(e))

        all_projects = []
        for projects in api.get_projects():
            all_projects.extend(projects)

        project_list = [
            {"project_id": p.id, "name": p.name}
            for p in all_projects
        ]
        project_list.sort(key=lambda x: x["project_id"])

        return format_success({"total": len(project_list), "projects": project_list})
