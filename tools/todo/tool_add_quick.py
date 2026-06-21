"""Tool: todo_add_quick — 使用 Quick Add 语法快速添加任务。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success
from tools.todo.todo_base import TodoAPIHelper


class TodoAddQuickInput(BaseModel):
    get_doc: bool = Field(
        default=False,
        description="设为 true 以获取 Todoist 领域知识文档",
    )
    text: str = Field(
        default="",
        description=(
            "Quick Add 语法文本。Todoist 会自动解析其中的 #项目 @标签 自然语言日期 p1-p4 优先级等。"
            " 例如：'买牛奶 #购物 @日用品 明天下午3点 p2'"
        ),
    )
    note: str | None = Field(
        default=None,
        description="附加备注/说明",
    )
    reminder: str | None = Field(
        default=None,
        description="提醒日期/时间的自然语言描述，例如 '30分钟前'、'明天上午9点'",
    )
    auto_reminder: bool = Field(
        default=True,
        description="如果设置了时间，自动添加默认提醒",
    )


class TodoAddQuickTool(ToolBase):
    name: str = "todo_add_quick"
    description: str = (
        "使用 Quick Add 语法快速向 Todoist 添加任务。"
        "支持在 text 中直接写 #项目名、@标签名、自然语言日期、p1-p4 优先级等。"
        "比 todo_add 更简洁，但无法精细控制所有字段。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = TodoAddQuickInput

    _helper: TodoAPIHelper | None = None

    @property
    def helper(self) -> TodoAPIHelper:
        if self._helper is None:
            self._helper = TodoAPIHelper(self.client._todoist_token)
        return self._helper

    def _run(
        self,
        get_doc: bool = False,
        text: str = "",
        note: str | None = None,
        reminder: str | None = None,
        auto_reminder: bool = True,
    ) -> str:
        if get_doc:
            return self._load_doc()

        if not text:
            return format_error("text 不能为空，请提供任务描述")

        try:
            api = self.helper.api
        except ValueError as e:
            return format_error(str(e))

        try:
            task = api.add_task_quick(
                text=text,
                note=note,
                reminder=reminder,
                auto_reminder=auto_reminder,
            )
            return format_success(self.helper.task_to_dict(task))
        except Exception as e:
            return format_error(f"快速添加任务失败: {e}")
