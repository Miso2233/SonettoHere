"""Tool: file_write — 写入/创建文件内容（执行前需用户确认放行）。"""

import os

from langchain_core.callbacks.manager import AsyncCallbackManagerForToolRun
from pydantic import BaseModel, Field

from tools.base import ToolBase, check_path_access, format_error, format_success
from tools.confirm import confirm_execution


class FileWriteInput(BaseModel):
    get_doc: bool = Field(
        default=False, description="设为 true 以获取使用说明和领域知识"
    )
    file_path: str = Field(default="", description="文件绝对路径")
    content: str = Field(default="", description="要写入的文件内容")


class FileWriteTool(ToolBase):
    name: str = "file_write"
    description: str = (
        "写入内容到文件（自动创建父目录）。执行前需用户确认放行。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = FileWriteInput

    def _run(
        self, get_doc: bool = False, file_path: str = "", content: str = ""
    ) -> str:
        raise NotImplementedError("file_write 仅支持异步模式，请使用 _arun")

    async def _arun(
        self,
        get_doc: bool = False,
        file_path: str = "",
        content: str = "",
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        """前置校验通过后交由确认门控执行（写文件前需用户放行）。

        get_doc / 空参数 / 路径安全校验在此先行短路，避免向用户弹出无效确认。
        """
        if get_doc:
            return self._load_doc()
        if not file_path:
            return format_error("写入文件需要提供 file_path")
        if not content:
            return format_error("写入文件需要提供 content")

        err = check_path_access(file_path)
        if err:
            return format_error(err)

        return await self._run_after_confirm(
            file_path=file_path, content=content, run_manager=run_manager
        )

    @confirm_execution(
        question="即将写入以下内容到文件，是否确认执行？",
        options=["允许写入", "拒绝"],
        extra_payload=lambda self, file_path, content, **kw: {
            "file_path": file_path,
            "content": content,
        },
        reject_message="用户拒绝写入文件",
    )
    async def _run_after_confirm(
        self,
        file_path: str,
        content: str,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        """（由 confirm_execution 门控）确认通过后写入文件。"""
        try:
            return self._write(file_path, content)
        except Exception as e:
            return format_error(str(e))

    def _write(self, file_path: str, content: str) -> str:
        """实际写入：自动创建父目录并落盘。"""
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
