"""Tool: file_list_directory — 列出目录内容。"""

import os

from pydantic import BaseModel, Field

from tools.base import (
    ToolBase,
    check_path_access,
    format_error,
    format_success,
    off_thread,
)


class FileListDirectoryInput(BaseModel):
    directory_path: str = Field(
        default="", description="目录路径（留空则列出当前目录）"
    )


class FileListDirectoryTool(ToolBase):
    name: str = "file_list_directory"
    description: str = (
        "列出目录内容（文件与子目录，含大小，目录优先排序）。"
        "[调用积极性: 可自由看情况调用]"
    )
    args_schema: type[BaseModel] = FileListDirectoryInput

    def _run(self, directory_path: str = "") -> str:
        raise NotImplementedError("file_list_directory 仅支持异步模式，请使用 _arun")

    async def _arun(self, directory_path: str = "") -> str:
        return await off_thread(self._run_impl, directory_path)

    def _run_impl(self, directory_path: str = "") -> str:
        if not directory_path:
            directory_path = "."
        if not os.path.exists(directory_path):
            return format_error(f"目录不存在: {directory_path}")
        if not os.path.isdir(directory_path):
            return format_error(f"路径不是目录: {directory_path}")

        err = check_path_access(directory_path)
        if err:
            return format_error(err)

        items = []
        for item in os.listdir(directory_path):
            item_path = os.path.join(directory_path, item)
            st = os.stat(item_path)
            items.append({
                "name": item,
                "path": item_path,
                "is_file": os.path.isfile(item_path),
                "is_dir": os.path.isdir(item_path),
                "size": st.st_size if os.path.isfile(item_path) else 0,
            })

        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

        return format_success({
            "directory": os.path.abspath(directory_path),
            "items": items,
            "count": len(items),
            "file_count": sum(1 for i in items if i["is_file"]),
            "dir_count": sum(1 for i in items if i["is_dir"]),
        })
