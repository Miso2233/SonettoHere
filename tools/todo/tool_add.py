"""Tool: todo_add — 向 Todoist 添加新任务。"""

from typing import Literal

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success
from tools.todo.todo_base import TodoAPIHelper


class TodoAddInput(BaseModel):
    """添加任务的输入参数"""

    get_doc: bool = Field(
        default=False,
        description="设为 true 以获取 Todoist 领域知识文档（首次使用或不确定参数规则时建议先调用）",
    )
    content: str = Field(default="", description="任务名称/内容，例如'完成项目报告'")
    description: str = Field(
        default="",
        description="任务描述/备注，例如详细的背景说明或 checklist",
    )
    due_string: str | None = Field(
        default=None,
        description=(
            "截止日期的自然语言描述，例如 next Monday、tomorrow at 3pm、every Friday"
            " 等。与 due_date / due_datetime 互斥，优先使用 due_string"
        ),
    )
    due_lang: str | None = Field(
        default=None,
        description="due_string 的解析语种，如 'en'（默认）、'zh' 等",
    )
    due_date: str | None = Field(
        default=None,
        description="截止日期。支持 YYYY-MM-DD 或 YYYY-MM-DD HH:MM 格式。与 due_string / due_datetime 互斥",
    )
    due_datetime: str | None = Field(
        default=None,
        description="精确截止时间，YYYY-MM-DD HH:MM 格式。与 due_string / due_date 互斥",
    )
    priority: int = Field(default=1, description="1=低, 2=中, 3=高, 4=紧急")
    project_name: str = Field(
        default="Inbox",
        description="所属项目名。务必先通过 todo_list_projects 确认项目存在",
    )
    section_name: str | None = Field(
        default=None,
        description=(
            "分区名（项目下的 section）。传入后会自动解析为 section_id。"
            " 务必先通过 todo_list_projects 查看项目的可用 section"
        ),
    )
    labels: list[str] | None = Field(
        default=None,
        description="标签名称列表，如 ['urgent', 'work']。注意是标签名而非 ID",
    )
    parent_id: str | None = Field(
        default=None,
        description="父任务 ID。用于创建子任务",
    )
    assignee_id: str | None = Field(
        default=None,
        description="指派给的用户 ID",
    )
    order: int | None = Field(
        default=None,
        description="任务在项目或分区中的排序位置",
    )
    auto_reminder: bool | None = Field(
        default=None,
        description="设为 true 则在设置了时间时自动添加默认提醒",
    )
    auto_parse_labels: bool | None = Field(
        default=None,
        description="设为 true 则从 content 中解析 #标签 和 @标签 语法",
    )
    duration: int | None = Field(
        default=None,
        description="预估时长数值（需配合 duration_unit 使用）",
    )
    duration_unit: Literal["minute", "day"] | None = Field(
        default=None,
        description="时长单位，'minute' 或 'day'",
    )
    deadline_date: str | None = Field(
        default=None,
        description="硬截止期限日期，YYYY-MM-DD 格式。与 due 不同，deadline 不绑定时间",
    )
    deadline_lang: str | None = Field(
        default=None,
        description="deadline_date 的解析语种",
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
        description: str = "",
        due_string: str | None = None,
        due_lang: str | None = None,
        due_date: str | None = None,
        due_datetime: str | None = None,
        priority: int = 1,
        project_name: str = "Inbox",
        section_name: str | None = None,
        labels: list[str] | None = None,
        parent_id: str | None = None,
        assignee_id: str | None = None,
        order: int | None = None,
        auto_reminder: bool | None = None,
        auto_parse_labels: bool | None = None,
        duration: int | None = None,
        duration_unit: Literal["minute", "day"] | None = None,
        deadline_date: str | None = None,
        deadline_lang: str | None = None,
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

        section_id = None
        if section_name:
            section_id = self.helper.get_section_id(section_name, project_id)
            if section_id is None:
                return format_error(
                    f"项目 '{project_name}' 下不存在分区 '{section_name}'。"
                    " 请先调用 todo_list_projects 查看可用分区"
                )

        try:
            description_val = description or None
            due_date_obj = None
            if due_date:
                parsed_due = self.helper.parse_date(due_date)
                if parsed_due:
                    due_date_obj = parsed_due.date()
            due_datetime_obj = (
                self.helper.parse_datetime(due_datetime) if due_datetime else None
            )
            deadline_date_obj = (
                self.helper.parse_deadline(deadline_date) if deadline_date else None
            )

            task = api.add_task(
                content=content,
                description=description_val,
                project_id=project_id,
                section_id=section_id,
                priority=priority,
                due_string=due_string,
                due_lang=due_lang,
                due_date=due_date_obj,
                due_datetime=due_datetime_obj,
                labels=labels,
                parent_id=parent_id,
                assignee_id=assignee_id,
                order=order,
                auto_reminder=auto_reminder,
                auto_parse_labels=auto_parse_labels,
                duration=duration,
                duration_unit=duration_unit,
                deadline_date=deadline_date_obj,
                deadline_lang=deadline_lang,
            )
            return format_success(self.helper.task_to_dict(task))
        except Exception as e:
            return format_error(f"添加任务失败: {e}")
