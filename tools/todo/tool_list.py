"""Tool: todo_list — 列出 Todoist 中所有未完成任务。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success
from tools.todo.todo_base import TodoAPIHelper


class TodoListInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    project_name: str | None = Field(
        default=None,
        description="按项目名筛选。先通过 todo_list_projects 确认项目名",
    )
    section_name: str | None = Field(
        default=None,
        description=(
            "按分区名筛选。可配合 project_name 一起使用，"
            "如果未传 project_name 则在所有项目中查找该分区名"
        ),
    )
    label: str | None = Field(
        default=None,
        description="按标签名筛选，例如 'urgent'、'work'",
    )
    parent_id: str | None = Field(
        default=None,
        description="按父任务 ID 筛选，只返回该任务的子任务",
    )
    ids: list[str] | None = Field(
        default=None,
        description="按任务 ID 列表精确查询，例如 ['id1', 'id2']",
    )
    limit: int | None = Field(
        default=None,
        description="返回数量上限（1-200）",
        ge=1,
        le=200,
    )


class TodoListTool(ToolBase):
    name: str = "todo_list"
    description: str = (
        "列出 Todoist 中所有未完成任务，支持按项目、分区、标签等条件筛选。"
        " [调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = TodoListInput

    _helper: TodoAPIHelper | None = None

    @property
    def helper(self) -> TodoAPIHelper:
        if self._helper is None:
            self._helper = TodoAPIHelper(self.client._todoist_token)
        return self._helper

    def _run(
        self,
        get_doc: bool = False,
        project_name: str | None = None,
        section_name: str | None = None,
        label: str | None = None,
        parent_id: str | None = None,
        ids: list[str] | None = None,
        limit: int | None = None,
    ) -> str:
        if get_doc:
            return self._load_doc()

        try:
            api = self.helper.api
        except ValueError as e:
            return format_error(str(e))

        # 构建过滤参数
        kwargs: dict = {}

        if project_name:
            pid = self.helper.get_project_id(project_name)
            if pid is None:
                return format_success({"total": 0, "tasks": []})
            kwargs["project_id"] = pid

        if section_name:
            if project_name:
                # 已知项目上下文
                sid = self.helper.get_section_id(
                    section_name, kwargs.get("project_id", "")
                )
                if sid is None:
                    return format_success({"total": 0, "tasks": []})
                kwargs["section_id"] = sid
            else:
                # 跨项目查找
                result = self.helper.find_section_global(section_name)
                if result is None:
                    return format_success({"total": 0, "tasks": []})
                kwargs["section_id"] = result[1]

        if label:
            kwargs["label"] = label
        if parent_id:
            kwargs["parent_id"] = parent_id
        if ids:
            kwargs["ids"] = ids
        if limit:
            kwargs["limit"] = limit

        all_tasks = []
        for tasks in api.get_tasks(**kwargs):
            all_tasks.extend(tasks)

        task_list = [self.helper.task_to_dict(t) for t in all_tasks]
        task_list.sort(key=lambda x: x["task_id"])

        return format_success({"total": len(task_list), "tasks": task_list})
