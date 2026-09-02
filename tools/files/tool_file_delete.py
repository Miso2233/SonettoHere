"""Tool: file_delete — 删除文件或目录（执行前需用户确认放行）。"""

import os
import shutil

from langchain_core.callbacks.manager import AsyncCallbackManagerForToolRun
from pydantic import BaseModel, Field

from tools.base import ToolBase, check_path_access, format_error, format_success
from tools.confirm import confirm_execution


class FileDeleteInput(BaseModel):
    get_doc: bool = Field(
        default=False, description="设为 true 以获取使用说明和领域知识"
    )
    file_path: str = Field(default="", description="要删除的文件或目录绝对路径")


class FileDeleteTool(ToolBase):
    name: str = "file_delete"
    description: str = (
        "删除文件或目录（文件用 os.remove，目录递归删除）。执行前需用户确认放行。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = FileDeleteInput

    def _run(self, get_doc: bool = False, file_path: str = "") -> str:
        raise NotImplementedError("file_delete 仅支持异步模式，请使用 _arun")

    async def _arun(
        self,
        get_doc: bool = False,
        file_path: str = "",
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        """前置校验通过后交由确认门控执行（删除前需用户放行）。

        get_doc / 空参数 / 路径存在性 / 安全检查在此先行短路。
        """
        if get_doc:
            return self._load_doc()
        if not file_path:
            return format_error("删除需要提供 file_path")
        if not os.path.exists(file_path):
            return format_error(f"文件不存在: {file_path}")

        err = check_path_access(file_path)
        if err:
            return format_error(err)

        return await self._run_after_confirm(file_path=file_path, run_manager=run_manager)

    @confirm_execution(
        question="即将删除以下路径，是否确认执行？此操作不可撤销。",
        options=["允许删除", "拒绝"],
        extra_payload=lambda self, file_path, **kw: {"file_path": file_path},
        reject_message="用户拒绝删除文件",
    )
    async def _run_after_confirm(
        self,
        file_path: str,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        """（由 confirm_execution 门控）确认通过后删除文件或目录。"""
        try:
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
        except Exception as e:
            return format_error(str(e))
