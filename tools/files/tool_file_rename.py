"""Tool: file_rename — 重命名/移动文件或目录（执行前需用户确认放行）。"""

import os

from langchain_core.callbacks.manager import AsyncCallbackManagerForToolRun
from pydantic import BaseModel, Field

from tools.base import ToolBase, check_path_access, format_error, format_success
from tools.confirm import confirm_execution


class FileRenameInput(BaseModel):
    get_doc: bool = Field(
        default=False, description="设为 true 以获取使用说明和领域知识"
    )
    file_path: str = Field(default="", description="源路径（文件或目录）")
    new_path: str = Field(default="", description="目标路径（重命名或移动后）")


class FileRenameTool(ToolBase):
    name: str = "file_rename"
    description: str = (
        "重命名或移动文件/目录到新路径。执行前需用户确认放行。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = FileRenameInput

    def _run(
        self, get_doc: bool = False, file_path: str = "", new_path: str = ""
    ) -> str:
        raise NotImplementedError("file_rename 仅支持异步模式，请使用 _arun")

    async def _arun(
        self,
        get_doc: bool = False,
        file_path: str = "",
        new_path: str = "",
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        """前置校验通过后交由确认门控执行（重命名前需用户放行）。"""
        if get_doc:
            return self._load_doc()
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

        return await self._run_after_confirm(
            file_path=file_path, new_path=new_path, run_manager=run_manager
        )

    @confirm_execution(
        question="即将重命名/移动文件，是否确认执行？",
        options=["允许重命名", "拒绝"],
        extra_payload=lambda self, file_path, new_path, **kw: {
            "file_path": file_path,
            "new_path": new_path,
        },
        reject_message="用户拒绝重命名文件",
    )
    async def _run_after_confirm(
        self,
        file_path: str,
        new_path: str,
        run_manager: AsyncCallbackManagerForToolRun | None = None,
    ) -> str:
        """（由 confirm_execution 门控）确认通过后重命名/移动。"""
        try:
            os.rename(file_path, new_path)
            return format_success({
                "message": f"已重命名: {file_path} → {new_path}",
                "old_path": file_path,
                "new_path": new_path,
            })
        except Exception as e:
            return format_error(str(e))
