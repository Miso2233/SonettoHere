"""Tool: file_read — 读取文件内容。"""

import os

from pydantic import BaseModel, Field

from tools.base import ToolBase, check_path_access, format_error, format_success


class FileReadInput(BaseModel):
    get_doc: bool = Field(
        default=False, description="设为 true 以获取使用说明和领域知识"
    )
    file_path: str = Field(default="", description="文件绝对路径")


class FileReadTool(ToolBase):
    name: str = "file_read"
    description: str = (
        "读取文件内容并返回完整文本。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = FileReadInput

    def _run(self, get_doc: bool = False, file_path: str = "") -> str:
        if get_doc:
            return self._load_doc()
        if not file_path:
            return format_error("读取文件需要提供 file_path")

        err = check_path_access(file_path)
        if err:
            return format_error(err)

        if not os.path.exists(file_path):
            return format_error(f"文件不存在: {file_path}")
        if not os.path.isfile(file_path):
            return format_error(f"路径不是文件: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = f.read()

        st = os.stat(file_path)
        return format_success({
            "content": data,
            "file_path": os.path.abspath(file_path),
            "file_info": {"size": st.st_size, "path": os.path.abspath(file_path)},
        })
