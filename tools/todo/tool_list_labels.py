"""Tool: todo_list_labels — 列出所有标签。"""

from pydantic import BaseModel

from tools.base import ToolBase, format_error, format_success
from tools.get_doc import get_doc
from tools.todo.todo_base import TodoAPIHelper


class TodoListLabelsInput(BaseModel):
    pass


@get_doc
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
            self._helper = TodoAPIHelper(self.client)
        return self._helper

    async def _arun(self) -> str:
        all_labels = await self.helper.get_all_labels()
        label_list = [self.helper.label_to_dict(l) for l in all_labels]
        label_list.sort(key=lambda x: x["name"])

        return format_success({"total": len(label_list), "labels": label_list})
