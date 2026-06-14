"""Tool: task_tracker — 会话内任务清单追踪。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success


class TaskTrackerInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    tasks: list[str] | None = Field(default=None, description="任务清单列表，建立新任务")
    next_step: bool = Field(default=False, description="设为 true 推进到下一步")


class TaskTrackerTool(ToolBase):
    name: str = "task_tracker"
    description: str = (
        "会话内任务清单追踪。传 tasks 列表建立任务并返回第一步，传 next_step=true 推进。"
        "★ 首次使用先 get_doc=true。"
    )
    args_schema: type[BaseModel] = TaskTrackerInput

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._tasks: list[str] = []
        self._current_step: int = -1

    def _run(
        self,
        get_doc: bool = False,
        tasks: list[str] | None = None,
        next_step: bool = False,
    ) -> str:
        if get_doc:
            return self._load_doc()

        if tasks is not None:
            self._tasks = tasks
            self._current_step = 0
            if self._tasks:
                return format_success({
                    "status": "initialized",
                    "total_steps": len(self._tasks),
                    "tasks": self._tasks,
                    "current_step": 1,
                    "current_task": self._tasks[0],
                })
            return format_error("任务清单为空")

        if next_step:
            if not self._tasks:
                return format_error("未建立任务清单，请先传入 tasks 参数")
            self._current_step += 1
            if self._current_step >= len(self._tasks):
                completed = len(self._tasks)
                self._tasks = []
                self._current_step = -1
                return format_success({"status": "completed", "total_steps": completed, "message": "所有任务已完成"})
            return format_success({
                "status": "in_progress",
                "total_steps": len(self._tasks),
                "current_step": self._current_step + 1,
                "current_task": self._tasks[self._current_step],
            })

        return format_error("请提供 tasks 参数建立任务，或设置 next_step=true 执行下一步")
