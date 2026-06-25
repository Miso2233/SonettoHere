"""Tool: file_manage — 管理文件和目录（删除/重命名/创建目录）。"""

import os
import shutil

from pydantic import BaseModel, Field

from tools.base import ToolBase, check_path_access, format_error, format_success


class FileManageInput(BaseModel):
    get_doc: bool = Field(
        default=False, description="设为 true 以获取使用说明和领域知识"
    )
    operation: str = Field(
        default="",
        description="操作类型: delete_file / rename_file / create_directory",
    )
    file_path: str = Field(
        default="", description="文件路径（delete_file / rename_file 操作）"
    )
    new_path: str = Field(default="", description="新路径（rename_file 操作）")
    directory_path: str = Field(
        default="", description="目录路径（create_directory 操作）"
    )


class FileManageTool(ToolBase):
    name: str = "file_manage"
    description: str = (
        "管理文件和目录：删除文件/目录、重命名文件、创建目录。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = FileManageInput

    def _run(
        self,
        get_doc: bool = False,
        operation: str = "",
        file_path: str = "",
        new_path: str = "",
        directory_path: str = "",
    ) -> str:
        if get_doc:
            return self._load_doc()
        if not operation:
            return format_error("operation 不能为空")

        if operation == "delete_file":
            return self._delete_file(file_path)
        elif operation == "rename_file":
            return self._rename_file(file_path, new_path)
        elif operation == "create_directory":
            return self._create_directory(directory_path)
        else:
            return format_error(f"未知的操作类型: {operation}")

    def _check(self, path: str) -> str | None:
        """对单个路径执行安全检查，返回错误信息或 None。"""
        err = check_path_access(path)
        if err:
            return format_error(err)
        return None

    def _delete_file(self, file_path: str) -> str:
        if not file_path:
            return format_error("删除文件需要提供 file_path")
        if not os.path.exists(file_path):
            return format_error(f"文件不存在: {file_path}")

        err = self._check(file_path)
        if err:
            return err

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

    def _rename_file(self, file_path: str, new_path: str) -> str:
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

        os.rename(file_path, new_path)
        return format_success({
            "message": f"已重命名: {file_path} → {new_path}",
            "old_path": file_path,
            "new_path": new_path,
        })

    def _create_directory(self, directory_path: str) -> str:
        if not directory_path:
            return format_error("创建目录需要提供 directory_path")

        err = self._check(directory_path)
        if err:
            return err

        os.makedirs(directory_path, exist_ok=True)
        return format_success({
            "message": f"目录已创建: {directory_path}",
            "directory_path": os.path.abspath(directory_path),
        })
