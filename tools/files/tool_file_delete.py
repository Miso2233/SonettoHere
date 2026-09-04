"""Tool: file_delete — 删除文件或目录（需用户确认放行后执行）。"""

import os
import shutil

from pydantic import BaseModel, Field

from tools.base import (
    ToolBase,
    check_path_access,
    format_error,
    format_success,
    off_thread,
)
from tools.confirm import confirm_execution


class FileDeleteInput(BaseModel):
    file_path: str = Field(default="", description="要删除的文件或目录绝对路径")


@confirm_execution(
    question="即将删除以下路径，是否确认执行？此操作不可撤销。",
    approve_text="允许删除",
    reject_text="拒绝",
    reject_message="用户拒绝删除文件",
)
class FileDeleteTool(ToolBase):
    name: str = "file_delete"
    description: str = (
        "删除文件或目录（文件用 os.remove，目录递归删除）。执行前需用户确认放行。"
        "[调用积极性: 可自由看情况调用]"
    )
    args_schema: type[BaseModel] = FileDeleteInput

    def _run(self, file_path: str = "") -> str:
        raise NotImplementedError("file_delete 仅支持异步模式，请使用 _arun")

    async def _arun(self, file_path: str = "") -> str:
        """用户确认放行后：离环执行校验与删除。"""
        return await off_thread(self._run_impl, file_path)

    def _run_impl(self, file_path: str = "") -> str:
        """校验并删除文件或目录。"""
        if not file_path:
            return format_error("删除需要提供 file_path")
        if not os.path.exists(file_path):
            return format_error(f"文件不存在: {file_path}")

        err = check_path_access(file_path)
        if err:
            return format_error(err)

        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
            else:
                return format_error(f"未知的文件类型: {file_path}")
        except OSError as e:
            return format_error(str(e))

        return format_success({
            "message": f"已删除: {file_path}",
            "file_path": file_path,
        })
