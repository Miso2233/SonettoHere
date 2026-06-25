"""Tool: file_search — 列出目录内容、搜索文件。"""

import glob
import os

from pydantic import BaseModel, Field

from tools.base import ToolBase, check_path_access, format_error, format_success


class FileSearchInput(BaseModel):
    get_doc: bool = Field(
        default=False, description="设为 true 以获取使用说明和领域知识"
    )
    operation: str = Field(
        default="",
        description="操作类型: list_directory / search_files",
    )
    directory_path: str = Field(
        default="", description="目录路径（list_directory 操作）"
    )
    search_pattern: str = Field(
        default="", description="搜索模式（search_files 操作），支持 glob 通配符"
    )
    recursive: bool = Field(
        default=False, description="是否递归搜索（search_files 操作）"
    )
    file_filter: str = Field(
        default="all",
        description="过滤器: all / files_only / directories_only / by_extension",
    )
    extension: str = Field(default="", description="扩展名过滤，如 '.py'")


class FileSearchTool(ToolBase):
    name: str = "file_search"
    description: str = (
        "列出目录内容或使用 glob 通配符搜索文件。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = FileSearchInput

    def _run(
        self,
        get_doc: bool = False,
        operation: str = "",
        directory_path: str = "",
        search_pattern: str = "",
        recursive: bool = False,
        file_filter: str = "all",
        extension: str = "",
    ) -> str:
        if get_doc:
            return self._load_doc()
        if not operation:
            return format_error("operation 不能为空")

        if operation == "list_directory":
            return self._list_directory(directory_path)
        elif operation == "search_files":
            return self._search_files(
                search_pattern, directory_path, recursive, file_filter, extension
            )
        else:
            return format_error(f"未知的操作类型: {operation}")

    def _list_directory(self, directory_path: str) -> str:
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

    def _search_files(
        self,
        pattern: str,
        directory: str,
        recursive: bool,
        file_filter: str,
        extension: str,
    ) -> str:
        if not pattern:
            pattern = "*"
        if not directory:
            directory = "."

        err = check_path_access(directory)
        if err:
            return format_error(err)

        if not os.path.exists(directory):
            return format_error(f"搜索目录不存在: {directory}")

        search_path = (
            os.path.join(directory, "**", pattern)
            if recursive
            else os.path.join(directory, pattern)
        )
        found = []
        for fp in glob.glob(search_path, recursive=recursive):
            if file_filter == "files_only" and not os.path.isfile(fp):
                continue
            if file_filter == "directories_only" and not os.path.isdir(fp):
                continue
            if (
                file_filter == "by_extension"
                and extension
                and not fp.lower().endswith(extension.lower())
            ):
                continue

            st = os.stat(fp)
            found.append({
                "path": fp,
                "name": os.path.basename(fp),
                "is_file": os.path.isfile(fp),
                "is_dir": os.path.isdir(fp),
                "size": st.st_size if os.path.isfile(fp) else 0,
            })

        found.sort(key=lambda x: x["path"].lower())
        return format_success({
            "search_pattern": pattern,
            "search_directory": os.path.abspath(directory),
            "recursive": recursive,
            "file_filter": file_filter,
            "found_files": found,
            "count": len(found),
        })
