"""Tool: todo_complete — 将任务标记为已完成。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success
from tools.get_doc import get_doc
from tools.todo.todo_base import TodoAPIHelper


class TodoCompleteInput(BaseModel):
    task_id: str = Field(default="", description="要完成的任务 ID")


@get_doc
class TodoCompleteTool(ToolBase):
    name: str = "todo_complete"
    description: str = "将 Todoist 中指定任务标记为已完成。需要提供 task_id。[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    args_schema: type[BaseModel] = TodoCompleteInput

    _helper: TodoAPIHelper | None = None

    @property
    def helper(self) -> TodoAPIHelper:
        if self._helper is None:
            self._helper = TodoAPIHelper(self.client)
        return self._helper

    async def _arun(self, task_id: str = "") -> str:
        if not task_id:
            return format_error("task_id 不能为空")

        try:
            api = self.helper.api
        except ValueError as e:
            return format_error(str(e))

        try:
            current_task = await api.get_task(task_id)
            ok = await api.complete_task(task_id)
            if ok:
                return format_success(
                    {
                        "task_id": task_id,
                        "content": current_task.content,
                        "message": "任务已标记为完成",
                    }
                )
            return format_error("标记任务完成失败")
        except Exception as e:
            return format_error(f"任务不存在或完成失败: {e}")
