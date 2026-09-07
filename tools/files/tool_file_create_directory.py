"""Tool: file_create_directory — 创建目录（需用户确认放行后执行）。"""

import os

from pydantic import BaseModel, Field

from tools.base import (
    ToolBase,
    format_error,
    format_success,
    off_thread,
)
from tools.confirm import confirm_execution
from tools.path_guard import PathSpec, path_guard


class FileCreateDirectoryInput(BaseModel):
    directory_path: str = Field(default="", description="要创建的目录路径")


@path_guard(PathSpec("directory_path", kind="dir", existence=None))
@confirm_execution(
    question="即将创建以下目录，是否确认执行？",
    approve_text="允许创建",
    reject_text="拒绝",
    reject_message="用户拒绝创建目录",
)
class FileCreateDirectoryTool(ToolBase):
    name: str = "file_create_directory"
    description: str = (
        "创建目录（自动创建所有必要的父目录，已存在时不做操作）。执行前需用户确认放行。"
        "[调用积极性: 可自由看情况调用]"
    )
    args_schema: type[BaseModel] = FileCreateDirectoryInput

    async def _arun(self, directory_path: str = "") -> str:
        """用户确认放行后：离环执行校验与创建目录。"""
        return await off_thread(self._run_impl, directory_path)

    def _run_impl(self, directory_path: str = "") -> str:
        """创建目录（含父目录；路径校验由 @path_guard 承接）。"""
        try:
            os.makedirs(directory_path, exist_ok=True)
        except OSError as e:
            return format_error(str(e))

        return format_success({
            "message": f"目录已创建: {directory_path}",
            "directory_path": os.path.abspath(directory_path),
        })
