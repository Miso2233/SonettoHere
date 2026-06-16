"""Tool: todo_update — 更新任务属性。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success
from tools.todo.todo_base import TodoAPIHelper


class TodoUpdateInput(BaseModel):
    get_doc: bool = Field(
        default=False,
        description="设为 true 以获取 Todoist 领域知识文档"
    )
    task_id: str = Field(default="", description="要更新的任务 ID")
    content: str | None = Field(default=None, description="新的任务名称")
    due_date: str | None = Field(
        default=None,
        description="新的截止日期，YYYY-MM-DD 或 YYYY-MM-DD HH:MM"
    )
    priority: int | None = Field(default=None, description="1=低, 2=中, 3=高, 4=紧急")
    project_name: str | None = Field(
        default=None,
        description="新的项目名（用于移动任务）。先通过 todo_list_projects 确认存在"
    )


class TodoUpdateTool(ToolBase):
    name: str = "todo_update"
    description: str = (
        "更新 Todoist 中现有任务的内容、截止日期、优先级或所属项目。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = TodoUpdateInput

    _helper: TodoAPIHelper | None = None

    @property
    def helper(self) -> TodoAPIHelper:
        if self._helper is None:
            self._helper = TodoAPIHelper(self.client._todoist_token)
        return self._helper

    def _run(
        self,
        get_doc: bool = False,
        task_id: str = "",
        content: str | None = None,
        due_date: str | None = None,
        priority: int | None = None,
        project_name: str | None = None,
    ) -> str:
        if get_doc:
            return self._load_doc()
        if not task_id:
            return format_error("task_id 不能为空")
        if priority is not None and priority not in [1, 2, 3, 4]:
            return format_error("priority 无效，有效值为: 1, 2, 3, 4")

        try:
            api = self.helper.api
        except ValueError as e:
            return format_error(str(e))

        try:
            current_task = api.get_task(task_id)

            # 如果需要移动项目
            if project_name:
                pid = self.helper.get_project_id(project_name)
                if pid is None:
                    return format_error(
                        f"项目 '{project_name}' 不存在。请先调用 todo_list_projects 查看可用项目"
                    )
                if pid != current_task.project_id:
                    api.move_task(task_id=task_id, project_id=pid)

            # 解析日期
            due_date_obj = None
            if due_date is not None:
                if due_date == "":
                    due_date_obj = None
                else:
                    due_date_obj = self.helper.parse_date(due_date)
                    if due_date_obj is None:
                        return format_error("due_date 格式错误，应为 YYYY-MM-DD 或 YYYY-MM-DD HH:MM")

            task = api.update_task(
                task_id=task_id,
                content=content,
                priority=priority,
                due_date=due_date_obj,
            )
            return format_success({
                "task_id": task.id,
                "content": task.content,
                "due_date": self.helper.format_due_date(task),
                "priority": task.priority,
                "project": self.helper.get_project_name(task.project_id),
            })
        except Exception as e:
            return format_error(f"任务不存在或更新失败: {e}")
