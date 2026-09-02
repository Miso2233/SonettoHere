"""Tool: file_create_directory — 创建目录（执行前需用户确认放行）。"""

import os

from langchain_core.callbacks.manager import AsyncCallbackManagerForToolRun
from pydantic import BaseModel, Field

from tools.base import ToolBase, check_path_access, format_error, format_success
from tools.confirm import confirm_execution


class FileCreateDirectoryInput(BaseModel):
    get_doc: bool = Field(
        default=False, description="设为 true 以获取使用说明和领域知识"
    )
    directory_path: str = Field(default="", description="要创建的目录路径")


class FileCreateDirectoryTool(ToolBase):
    name: str = "file_create_directory"
    description: str = (
        "创建目录（自动创建所有必要的父目录，已存在时不做操作）。执行前需用户确认放行。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = FileCreateDirectoryInput

    def _run(self, get_doc: bool = False, directory_path: str = "") -> str:
        raise NotImplementedError("file_create_directory 仅支持异步模式，请使用 _arun")

    async def _arun(
        self,
        get_doc: bool = False,
        directory_path: str = "",
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        """前置校验通过后交由确认门控执行（创建目录前需用户放行）。"""
        if get_doc:
            return self._load_doc()
        if not directory_path:
            return format_error("创建目录需要提供 directory_path")

        err = check_path_access(directory_path)
        if err:
            return format_error(err)

        return await self._run_after_confirm(
            directory_path=directory_path, run_manager=run_manager
        )

    @confirm_execution(
        question="即将创建以下目录，是否确认执行？",
        options=["允许创建", "拒绝"],
        extra_payload=lambda self, directory_path, **kw: {
            "directory_path": directory_path,
        },
        reject_message="用户拒绝创建目录",
    )
    async def _run_after_confirm(
        self,
        directory_path: str,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        """（由 confirm_execution 门控）确认通过后创建目录。"""
        try:
            os.makedirs(directory_path, exist_ok=True)
            return format_success({
                "message": f"目录已创建: {directory_path}",
                "directory_path": os.path.abspath(directory_path),
            })
        except Exception as e:
            return format_error(str(e))
