"""Tool: file_rename — 重命名/移动文件或目录（需用户确认放行后执行）。"""

import os

from pydantic import BaseModel, Field

from tools.base import ToolBase, check_path_access, format_error, format_success
from tools.confirm import confirm_execution


class FileRenameInput(BaseModel):
    file_path: str = Field(default="", description="源路径（文件或目录）")
    new_path: str = Field(default="", description="目标路径（重命名或移动后）")


@confirm_execution(
    question="即将重命名/移动文件，是否确认执行？",
    approve_text="允许重命名",
    reject_text="拒绝",
    reject_message="用户拒绝重命名文件",
)
class FileRenameTool(ToolBase):
    name: str = "file_rename"
    description: str = (
        "重命名或移动文件/目录到新路径。执行前需用户确认放行。"
        "[调用积极性: 可自由看情况调用]"
    )
    args_schema: type[BaseModel] = FileRenameInput

    def _run(self, file_path: str = "", new_path: str = "") -> str:
        raise NotImplementedError("file_rename 仅支持异步模式，请使用 _arun")

    async def _arun(self, file_path: str = "", new_path: str = "") -> str:
        """用户确认放行后：校验并重命名/移动。"""
        if not file_path:
            return format_error("重命名需要提供 file_path")
        if not new_path:
            return format_error("重命名需要提供 new_path")
        if not os.path.exists(file_path):
            return format_error(f"文件不存在: {file_path}")
        if os.path.exists(new_path):
            return format_error(f"目标已存在: {new_path}")

        for p in (file_path, new_path):
            err = check_path_access(p)
            if err:
                return format_error(err)

        try:
            os.rename(file_path, new_path)
        except OSError as e:
            return format_error(str(e))

        return format_success({
            "message": f"已重命名: {file_path} → {new_path}",
            "old_path": file_path,
            "new_path": new_path,
        })
