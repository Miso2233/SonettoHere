"""Tool: file_write — 写入/创建文件内容。"""

import os

from pydantic import BaseModel, Field

from tools.base import ToolBase, check_path_access, format_error, format_success


class FileWriteInput(BaseModel):
    get_doc: bool = Field(
        default=False, description="设为 true 以获取使用说明和领域知识"
    )
    file_path: str = Field(default="", description="文件绝对路径")
    content: str = Field(default="", description="要写入的文件内容")


class FileWriteTool(ToolBase):
    name: str = "file_write"
    description: str = (
        "写入内容到文件（自动创建父目录）。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = FileWriteInput

    def _run(
        self, get_doc: bool = False, file_path: str = "", content: str = ""
    ) -> str:
        if get_doc:
            return self._load_doc()
        if not file_path:
            return format_error("写入文件需要提供 file_path")
        if not content:
            return format_error("写入文件需要提供 content")

        err = check_path_access(file_path)
        if err:
            return format_error(err)

        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return format_success({
            "message": f"文件已写入: {file_path}",
            "file_path": os.path.abspath(file_path),
            "size": len(content),
            "line_count": content.count("\n") + 1,
        })
