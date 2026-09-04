"""Tool: todo_list_projects — 列出所有项目。"""

from pydantic import BaseModel

from tools.base import ToolBase, format_error, format_success
from tools.get_doc import get_doc
from tools.todo.todo_base import TodoAPIHelper


class TodoListProjectsInput(BaseModel):
    pass


@get_doc
class TodoListProjectsTool(ToolBase):
    name: str = "todo_list_projects"
    description: str = "列出 Todoist 中所有项目及其详细信息。添加任务前建议先调用以确认项目名。[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    args_schema: type[BaseModel] = TodoListProjectsInput

    _helper: TodoAPIHelper | None = None

    @property
    def helper(self) -> TodoAPIHelper:
        if self._helper is None:
            self._helper = TodoAPIHelper(self.client)
        return self._helper

    async def _arun(self) -> str:
        try:
            api = self.helper.api
        except ValueError as e:
            return format_error(str(e))

        all_projects = []
        async for projects in await api.get_projects():
            all_projects.extend(projects)

        project_list = [self.helper.project_to_dict(p) for p in all_projects]
        project_list.sort(key=lambda x: x["project_id"])

        return format_success({"total": len(project_list), "projects": project_list})
