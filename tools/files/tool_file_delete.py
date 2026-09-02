"""Tool: file_delete — 删除文件或目录。"""

import os
import shutil

from pydantic import BaseModel, Field

from tools.base import ToolBase, check_path_access, format_error, format_success


class FileDeleteInput(BaseModel):
    get_doc: bool = Field(
        default=False, description="设为 true 以获取使用说明和领域知识"
    )
    file_path: str = Field(default="", description="要删除的文件或目录绝对路径")


class FileDeleteTool(ToolBase):
    name: str = "file_delete"
    description: str = (
        "删除文件或目录（文件用 os.remove，目录递归删除）。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = FileDeleteInput

    def _run(self, get_doc: bool = False, file_path: str = "") -> str:
        if get_doc:
            return self._load_doc()
        if not file_path:
            return format_error("删除需要提供 file_path")
        if not os.path.exists(file_path):
            return format_error(f"文件不存在: {file_path}")

        err = check_path_access(file_path)
        if err:
            return format_error(err)

        if os.path.isfile(file_path):
            os.remove(file_path)
        elif os.path.isdir(file_path):
            shutil.rmtree(file_path)
        else:
            return format_error(f"未知的文件类型: {file_path}")

        return format_success({
            "message": f"已删除: {file_path}",
            "file_path": file_path,
        })
