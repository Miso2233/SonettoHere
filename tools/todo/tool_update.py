"""Tool: todo_update — 更新任务属性。"""

from typing import Literal

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success
from tools.todo.todo_base import TodoAPIHelper


class TodoUpdateInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取 Todoist 领域知识文档")
    task_id: str = Field(default="", description="要更新的任务 ID")
    content: str | None = Field(default=None, description="新的任务名称")
    description: str | None = Field(default=None, description="新的任务描述/备注")
    due_string: str | None = Field(
        default=None,
        description="截止日期的自然语言描述，例如 next Monday、tomorrow at 3pm",
    )
    due_lang: str | None = Field(default=None, description="due_string 的解析语种")
    due_date: str | None = Field(
        default=None,
        description="新的截止日期，YYYY-MM-DD 或 YYYY-MM-DD HH:MM。传空字符串 '' 可清除现有日期",
    )
    due_datetime: str | None = Field(
        default=None,
        description="新的精确截止时间，YYYY-MM-DD HH:MM 格式",
    )
    priority: int | None = Field(default=None, description="1=低, 2=中, 3=高, 4=紧急")
    labels: list[str] | None = Field(default=None, description="新的标签列表（覆盖原有标签）")
    assignee_id: str | None = Field(default=None, description="重新指派给的用户 ID")
    order: int | None = Field(default=None, description="在项目/分区中的排序位置")
    day_order: int | None = Field(default=None, description="在今日/最近7天视图中的排序位置")
    collapsed: bool | None = Field(default=None, description="是否折叠子任务")
    duration: int | None = Field(default=None, description="预估时长数值")
    duration_unit: Literal["minute", "day"] | None = Field(
        default=None, description="时长单位，'minute' 或 'day'"
    )
    deadline_date: str | None = Field(
        default=None, description="新的硬截止期限日期 YYYY-MM-DD"
    )
    deadline_lang: str | None = Field(default=None, description="deadline_date 的解析语种")

    # 移动相关
    project_name: str | None = Field(
        default=None,
        description="新的项目名（用于移动任务）。先通过 todo_list_projects 确认存在",
    )
    section_name: str | None = Field(
        default=None,
        description=(
            "新的分区名（用于将任务移动到另一分区）。"
            " 如果同时传了 project_name 则在该项目中查找，否则在当前项目中查找"
        ),
    )


class TodoUpdateTool(ToolBase):
    name: str = "todo_update"
    description: str = (
        "更新 Todoist 中现有任务的内容、截止日期、优先级、描述、标签、指派等属性，"
        "或将任务移动到其他项目/分区。"
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
        description: str | None = None,
        due_string: str | None = None,
        due_lang: str | None = None,
        due_date: str | None = None,
        due_datetime: str | None = None,
        priority: int | None = None,
        labels: list[str] | None = None,
        assignee_id: str | None = None,
        order: int | None = None,
        day_order: int | None = None,
        collapsed: bool | None = None,
        duration: int | None = None,
        duration_unit: Literal["minute", "day"] | None = None,
        deadline_date: str | None = None,
        deadline_lang: str | None = None,
        project_name: str | None = None,
        section_name: str | None = None,
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

            # ── 移动逻辑：project 和/或 section ──
            move_kwargs: dict[str, str] = {}
            section_target_project: str | None = None

            if project_name:
                pid = self.helper.get_project_id(project_name)
                if pid is None:
                    return format_error(
                        f"项目 '{project_name}' 不存在。请先调用 todo_list_projects 查看可用项目"
                    )
                if pid != current_task.project_id:
                    move_kwargs["project_id"] = pid
                section_target_project = pid

            if section_name:
                ctx_project = section_target_project or current_task.project_id
                sid = self.helper.get_section_id(section_name, ctx_project)
                if sid is None:
                    return format_error(
                        f"项目 '{self.helper.get_project_name(ctx_project)}'"
                        f" 下不存在分区 '{section_name}'"
                    )
                # section 隐式关联了 project，传 section_id 即可
                move_kwargs["section_id"] = sid

            if move_kwargs:
                api.move_task(task_id=task_id, **move_kwargs)

            # ── 字段更新 ──
            parsed_due_date = None
            if due_date:
                parsed = self.helper.parse_date(due_date)
                parsed_due_date = parsed.date() if parsed else None

            due_datetime_obj = (
                self.helper.parse_datetime(due_datetime) if due_datetime else None
            )
            deadline_date_obj = (
                self.helper.parse_deadline(deadline_date) if deadline_date else None
            )

            task = api.update_task(
                task_id=task_id,
                content=content,
                description=description,
                labels=labels,
                priority=priority,
                due_string=due_string,
                due_lang=due_lang,
                due_date=parsed_due_date,
                due_datetime=due_datetime_obj,
                assignee_id=assignee_id,
                order=order,
                day_order=day_order,
                collapsed=collapsed,
                duration=duration,
                duration_unit=duration_unit,
                deadline_date=deadline_date_obj,
                deadline_lang=deadline_lang,
            )
            return format_success(self.helper.task_to_dict(task))
        except Exception as e:
            return format_error(f"任务不存在或更新失败: {e}")
