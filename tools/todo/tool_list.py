"""Tool: todo_list — 列出 Todoist 中所有未完成任务。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success
from tools.todo.todo_base import TodoAPIHelper


class TodoListInput(BaseModel):
    get_doc: bool = Field(
        default=False,
        description="设为 true 以获取使用说明"
    )


class TodoListTool(ToolBase):
    name: str = "todo_list"
    description: str = "列出 Todoist 中所有未完成任务，按 ID 排序。直接调用即可。[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    args_schema: type[BaseModel] = TodoListInput

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

        all_tasks = []
        for tasks in api.get_tasks():
            all_tasks.extend(tasks)

        task_list = []
        for task in all_tasks:
            task_list.append({
                "task_id": task.id,
                "content": task.content,
                "due_date": self.helper.format_due_date(task),
                "priority": task.priority,
                "project": self.helper.get_project_name(task.project_id),
                "is_completed": task.is_completed,
            })
        task_list.sort(key=lambda x: x["task_id"])

        return format_success({"total": len(task_list), "tasks": task_list})
