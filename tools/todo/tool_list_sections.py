"""Tool: todo_list_sections — 列出分区。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success
from tools.todo.todo_base import TodoAPIHelper


class TodoListSectionsInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    project_name: str | None = Field(
        default=None,
        description="按项目名筛选。不传则列出所有项目的分区",
    )


class TodoListSectionsTool(ToolBase):
    name: str = "todo_list_sections"
    description: str = (
        "列出 Todoist 中的分区（section），可按项目筛选。"
        "添加或移动任务到特定分区前建议先调用此工具确认分区名。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = TodoListSectionsInput

    _helper: TodoAPIHelper | None = None

    @property
    def helper(self) -> TodoAPIHelper:
        if self._helper is None:
            self._helper = TodoAPIHelper(self.client._todoist_token)
        return self._helper

    def _run(self, get_doc: bool = False, project_name: str | None = None) -> str:
        if get_doc:
            return self._load_doc()

        if project_name:
            pid = self.helper.get_project_id(project_name)
            if pid is None:
                return format_error(
                    f"项目 '{project_name}' 不存在。请先调用 todo_list_projects 查看可用项目"
                )
            all_sections = self.helper.get_sections_by_project(project_name)
        else:
            all_sections = self.helper.get_all_sections()

        section_list = [self.helper.section_to_dict(s) for s in all_sections]
        section_list.sort(key=lambda x: x["section_id"])

        return format_success({"total": len(section_list), "sections": section_list})
