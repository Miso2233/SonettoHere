"""Tool: file_search — 使用 glob 通配符搜索文件。"""

import glob
import os

from pydantic import BaseModel, Field

from tools.base import (
    ToolBase,
    check_path_access,
    format_error,
    format_success,
    off_thread,
)
from tools.background import background


class FileSearchInput(BaseModel):
    search_pattern: str = Field(
        default="", description="搜索模式，支持 glob 通配符（如 *.py、**/*.md）"
    )
    directory_path: str = Field(default="", description="搜索目录（留空则为当前目录）")
    recursive: bool = Field(default=False, description="是否递归搜索（需配合 **/* 语法）")
    file_filter: str = Field(
        default="all",
        description="过滤器: all / files_only / directories_only / by_extension",
    )
    extension: str = Field(default="", description="扩展名过滤，如 '.py'")


@background
class FileSearchTool(ToolBase):
    name: str = "file_search"
    description: str = (
        "使用 glob 通配符在目录中搜索文件。"
        "[调用积极性: 可自由看情况调用]"
    )
    args_schema: type[BaseModel] = FileSearchInput

    def _run(
        self,
        search_pattern: str = "",
        directory_path: str = "",
        recursive: bool = False,
        file_filter: str = "all",
        extension: str = "",
    ) -> str:
        raise NotImplementedError("file_search 仅支持异步模式，请使用 _arun")

    async def _arun(
        self,
        search_pattern: str = "",
        directory_path: str = "",
        recursive: bool = False,
        file_filter: str = "all",
        extension: str = "",
    ) -> str:
        return await off_thread(
            self._search_files,
            search_pattern,
            directory_path,
            recursive,
            file_filter,
            extension,
        )

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
