"""Tool: todo_add — 向 Todoist 添加新任务。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success
from tools.todo.todo_base import TodoAPIHelper


class TodoAddInput(BaseModel):
    """添加任务的输入参数"""
    get_doc: bool = Field(
        default=False,
        description="设为 true 以获取 Todoist 领域知识文档（首次使用或不确定参数规则时建议先调用）"
    )
    content: str = Field(
        default="",
        description="任务名称/内容，例如'完成项目报告'"
    )
    due_date: str | None = Field(
        default=None,
        description="截止日期。支持自然语言（明天下午3点、下周五）或 YYYY-MM-DD HH:MM"
    )
    priority: int = Field(
        default=1,
        description="1=低, 2=中, 3=高, 4=紧急"
    )
    project_name: str = Field(
        default="Inbox",
        description="所属项目名。务必先通过 todo_list_projects 确认项目存在"
    )


class TodoAddTool(ToolBase):
    name: str = "todo_add"
    description: str = (
        "向 Todoist 添加新任务。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = TodoAddInput

    _helper: TodoAPIHelper | None = None

    @property
    def helper(self) -> TodoAPIHelper:
        if self._helper is None:
            self._helper = TodoAPIHelper(self.client._todoist_token)
        return self._helper

    def _run(
        self,
        get_doc: bool = False,
        content: str = "",
        due_date: str | None = None,
        priority: int = 1,
        project_name: str = "Inbox",
    ) -> str:
        if get_doc:
            return self._load_doc()

        if not content:
            return format_error("content 不能为空，请提供任务名称")

        if priority not in [1, 2, 3, 4]:
            return format_error("priority 无效，有效值为: 1, 2, 3, 4")

        try:
            api = self.helper.api
        except ValueError as e:
            return format_error(str(e))

        project_id = self.helper.get_project_id(project_name)
        if project_id is None:
            return format_error(
                f"项目 '{project_name}' 不存在。请先调用 todo_list_projects 查看可用项目"
            )

        try:
            due_date_obj = self.helper.parse_date(due_date) if due_date else None
            task = api.add_task(
                content=content,
                project_id=project_id,
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
            return format_error(f"添加任务失败: {e}")
