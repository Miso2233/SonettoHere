"""Tool: todo_query — 查询单个任务详情。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success
from tools.todo.todo_base import TodoAPIHelper


class TodoQueryInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    task_id: str = Field(default="", description="要查询的任务 ID")


class TodoQueryTool(ToolBase):
    name: str = "todo_query"
    description: str = "根据 task_id 查询 Todoist 中单个任务的详细信息。查不到时用 todo_list 列出全部任务。[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    args_schema: type[BaseModel] = TodoQueryInput

    _helper: TodoAPIHelper | None = None

    @property
    def helper(self) -> TodoAPIHelper:
        if self._helper is None:
            self._helper = TodoAPIHelper(self.client._todoist_token)
        return self._helper

    def _run(self, get_doc: bool = False, task_id: str = "") -> str:
        if get_doc:
            return self._load_doc()
        if not task_id:
            return format_error("task_id 不能为空")

        try:
            api = self.helper.api
        except ValueError as e:
            return format_error(str(e))

        try:
            task = api.get_task(task_id)
            return format_success({
                "task_id": task.id,
                "content": task.content,
                "due_date": self.helper.format_due_date(task),
                "priority": task.priority,
                "project": self.helper.get_project_name(task.project_id),
                "is_completed": task.is_completed,
            })
        except Exception as e:
            return format_error(f"任务不存在: {e}")
