"""Tool: file_create_directory — 创建目录（需用户确认放行后执行）。"""

import os

from pydantic import BaseModel, Field

from tools.base import ToolBase, check_path_access, format_error, format_success
from tools.confirm import confirm_execution


class FileCreateDirectoryInput(BaseModel):
    directory_path: str = Field(default="", description="要创建的目录路径")


class FileCreateDirectoryTool(ToolBase):
    name: str = "file_create_directory"
    description: str = (
        "创建目录（自动创建所有必要的父目录，已存在时不做操作）。执行前需用户确认放行。"
        "[调用积极性: 可自由看情况调用]"
    )
    args_schema: type[BaseModel] = FileCreateDirectoryInput

    def _run(self, directory_path: str = "") -> str:
        raise NotImplementedError("file_create_directory 仅支持异步模式，请使用 _arun")

    @confirm_execution(
        question="即将创建以下目录，是否确认执行？",
        options=["允许创建", "拒绝"],
        extra_payload=lambda self, directory_path: {
            "directory_path": directory_path,
        },
        reject_message="用户拒绝创建目录",
    )
    async def _arun(self, directory_path: str = "") -> str:
        """用户确认放行后：校验并创建目录（含父目录）。"""
        if not directory_path:
            return format_error("创建目录需要提供 directory_path")

        err = check_path_access(directory_path)
        if err:
            return format_error(err)

        try:
            os.makedirs(directory_path, exist_ok=True)
        except OSError as e:
            return format_error(str(e))

        return format_success({
            "message": f"目录已创建: {directory_path}",
            "directory_path": os.path.abspath(directory_path),
        })
