"""Tool: todo_list_labels — 列出所有标签。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success
from tools.todo.todo_base import TodoAPIHelper


class TodoListLabelsInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")


class TodoListLabelsTool(ToolBase):
    name: str = "todo_list_labels"
    description: str = (
        "列出 Todoist 中所有标签。添加任务前可通过此工具确认可用的标签名。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = TodoListLabelsInput

    _helper: TodoAPIHelper | None = None

    @property
    def helper(self) -> TodoAPIHelper:
        if self._helper is None:
            self._helper = TodoAPIHelper(self.client._todoist_token)
        return self._helper

    def _run(self, get_doc: bool = False) -> str:
        if get_doc:
            return self._load_doc()

        all_labels = self.helper.get_all_labels()
        label_list = [self.helper.label_to_dict(l) for l in all_labels]
        label_list.sort(key=lambda x: x["name"])

        return format_success({"total": len(label_list), "labels": label_list})
