"""Tool: file_create_directory — 创建目录。"""

import os

from pydantic import BaseModel, Field

from tools.base import ToolBase, check_path_access, format_error, format_success


class FileCreateDirectoryInput(BaseModel):
    get_doc: bool = Field(
        default=False, description="设为 true 以获取使用说明和领域知识"
    )
    directory_path: str = Field(default="", description="要创建的目录路径")


class FileCreateDirectoryTool(ToolBase):
    name: str = "file_create_directory"
    description: str = (
        "创建目录（自动创建所有必要的父目录，已存在时不做操作）。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = FileCreateDirectoryInput

    def _run(self, get_doc: bool = False, directory_path: str = "") -> str:
        if get_doc:
            return self._load_doc()
        if not directory_path:
            return format_error("创建目录需要提供 directory_path")

        err = check_path_access(directory_path)
        if err:
            return format_error(err)

        os.makedirs(directory_path, exist_ok=True)
        return format_success({
            "message": f"目录已创建: {directory_path}",
            "directory_path": os.path.abspath(directory_path),
        })
