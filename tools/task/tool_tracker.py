"""Tool: task_tracker — 无状态任务清单追踪。

LLM 每次调用传入全量 todos 列表，工具仅做统计和摘要返回。
不再维护内部状态机。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success


class TodoItem(BaseModel):
    content: str = Field(description="任务描述")
    status: str = Field(description="状态: pending | in_progress | completed")
    activeForm: str | None = Field(default=None, description="进行中的动名词描述")


class TaskTrackerInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    todos: list[TodoItem] | None = Field(default=None, description="全量任务清单，每次传入完整列表")


class TaskTrackerTool(ToolBase):
    name: str = "task_tracker"
    description: str = (
        "无状态任务清单追踪。每次传入完整的 todos 列表，工具返回统计摘要。"
        "[调用积极性: 可自由看情况调用] [get_doc: 使用前必须 get_doc]"
    )
    args_schema: type[BaseModel] = TaskTrackerInput

    def _run(
        self,
        get_doc: bool = False,
        todos: list[TodoItem] | None = None,
    ) -> str:
        if get_doc:
            return self._load_doc()

        if not todos:
            return format_error("请传入 todos 参数（全量任务清单）")

        total = len(todos)
        pending = sum(1 for t in todos if t.status == "pending")
        in_progress_count = sum(1 for t in todos if t.status == "in_progress")
        completed = sum(1 for t in todos if t.status == "completed")

        current_task = next(
            (t.content for t in todos if t.status == "in_progress"),
            None,
        )

        return format_success({
            "total": total,
            "pending": pending,
            "in_progress": in_progress_count,
            "completed": completed,
            "current_task": current_task,
            "todos": [t.model_dump() for t in todos],
        })
