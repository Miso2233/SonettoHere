"""Tool: file_read — 读取文件内容。"""

import os

from pydantic import BaseModel, Field

from tools.base import ToolBase, check_path_access, format_error, format_success


class FileReadInput(BaseModel):
    file_path: str = Field(default="", description="文件绝对路径")


class FileReadTool(ToolBase):
    name: str = "file_read"
    description: str = (
        "读取文件内容并返回完整文本。"
        "仅支持 UTF-8 编码的文本文件，非 UTF-8 文件（如二进制、GBK 编码）会返回错误提示。"
        "[调用积极性: 可自由看情况调用]"
    )
    args_schema: type[BaseModel] = FileReadInput

    def _run(self, file_path: str = "") -> str:
        if not file_path:
            return format_error("读取文件需要提供 file_path")

        err = check_path_access(file_path)
        if err:
            return format_error(err)

        if not os.path.exists(file_path):
            return format_error(f"文件不存在: {file_path}")
        if not os.path.isfile(file_path):
            return format_error(f"路径不是文件: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = f.read()
        except UnicodeDecodeError:
            return format_error(
                f"文件编码错误: 文件 '{file_path}' 不是有效的 UTF-8 编码，"
                "无法以文本方式读取。请确认文件编码或以二进制方式处理。"
            )

        st = os.stat(file_path)
        return format_success({
            "content": data,
            "file_path": os.path.abspath(file_path),
            "file_info": {"size": st.st_size, "path": os.path.abspath(file_path)},
        })
