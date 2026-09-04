"""Tool: todo_uncomplete — 取消任务完成状态。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success
from tools.get_doc import get_doc
from tools.todo.todo_base import TodoAPIHelper


class TodoUncompleteInput(BaseModel):
    task_id: str = Field(default="", description="要重新打开的任务 ID")


@get_doc
class TodoUncompleteTool(ToolBase):
    name: str = "todo_uncomplete"
    description: str = "将 Todoist 中已完成的任务重新打开。需要提供 task_id。[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    args_schema: type[BaseModel] = TodoUncompleteInput

    _helper: TodoAPIHelper | None = None

    @property
    def helper(self) -> TodoAPIHelper:
        if self._helper is None:
            self._helper = TodoAPIHelper(self.client)
        return self._helper

    def _run(self, task_id: str = "") -> str:
        raise NotImplementedError("todo_uncomplete 仅支持异步模式，请使用 _arun")

    async def _arun(self, task_id: str = "") -> str:
        if not task_id:
            return format_error("task_id 不能为空")

        try:
            api = self.helper.api
        except ValueError as e:
            return format_error(str(e))

        try:
            current_task = await api.get_task(task_id)
            ok = await api.uncomplete_task(task_id)
            if ok:
                return format_success(
                    {
                        "task_id": task_id,
                        "content": current_task.content,
                        "message": "任务已重新打开",
                    }
                )
            return format_error("重新打开任务失败")
        except Exception as e:
            return format_error(f"任务不存在或重新打开失败: {e}")
