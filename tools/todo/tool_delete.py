"""Tool: todo_delete — 删除指定任务。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success
from tools.todo.todo_base import TodoAPIHelper


class TodoDeleteInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    task_id: str = Field(default="", description="要删除的任务 ID")


class TodoDeleteTool(ToolBase):
    name: str = "todo_delete"
    description: str = "从 Todoist 删除指定任务。需要提供 task_id。[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    args_schema: type[BaseModel] = TodoDeleteInput

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
            ok = api.delete_task(task_id)
            if ok:
                return format_success({"task_id": task_id, "message": "任务删除成功"})
            return format_error("删除任务失败")
        except Exception as e:
            return format_error(f"任务不存在: {e}")
