"""Tool: file_write — 写入/创建文件内容（需用户确认放行后执行）。"""

import os

from pydantic import BaseModel, Field

from tools.base import ToolBase, check_path_access, format_error, format_success
from tools.confirm import confirm_execution


class FileWriteInput(BaseModel):
    file_path: str = Field(default="", description="文件绝对路径")
    content: str = Field(default="", description="要写入的文件内容")


class FileWriteTool(ToolBase):
    name: str = "file_write"
    description: str = (
        "写入内容到文件（自动创建父目录）。执行前需用户确认放行。"
        "[调用积极性: 可自由看情况调用]"
    )
    args_schema: type[BaseModel] = FileWriteInput

    def _run(self, file_path: str = "", content: str = "") -> str:
        raise NotImplementedError("file_write 仅支持异步模式，请使用 _arun")

    @confirm_execution(
        question="即将写入以下内容到文件，是否确认执行？",
        options=["允许写入", "拒绝"],
        reject_message="用户拒绝写入文件",
    )
    async def _arun(self, file_path: str = "", content: str = "") -> str:
        """用户确认放行后：校验并写入（自动创建父目录）。"""
        if not file_path:
            return format_error("写入文件需要提供 file_path")
        if not content:
            return format_error("写入文件需要提供 content")

        err = check_path_access(file_path)
        if err:
            return format_error(err)

        try:
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as e:
            return format_error(str(e))

        return format_success({
            "message": f"文件已写入: {file_path}",
            "file_path": os.path.abspath(file_path),
            "size": len(content),
            "line_count": content.count("\n") + 1,
        })
