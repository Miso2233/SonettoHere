"""Tool: file_operations — 文件系统操作。"""

import glob
import os
import shutil

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success


class FileOpsInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明和领域知识")
    operation: str = Field(
        default="",
        description="操作类型: read_file/write_file/delete_file/rename_file/create_directory/list_directory/search_files",
    )
    file_path: str = Field(default="", description="文件路径（read/write/delete/rename 操作）")
    content: str = Field(default="", description="写入内容（write_file 操作）")
    new_path: str = Field(default="", description="新路径（rename_file 操作）")
    directory_path: str = Field(default="", description="目录路径（create_directory/list_directory 操作）")
    search_pattern: str = Field(default="", description="搜索模式（search_files 操作），支持 glob 通配符")
    search_directory: str = Field(default=".", description="搜索根目录（search_files 操作）")
    recursive: bool = Field(default=False, description="是否递归搜索（search_files 操作）")
    file_filter: str = Field(default="all", description="过滤器: all/files_only/directories_only/by_extension")
    extension: str = Field(default="", description="扩展名过滤，如 '.py'")


class FileOperationsTool(ToolBase):
    name: str = "file_operations"
    description: str = (
        "文件系统操作：读取/写入/删除/重命名文件、创建/列出目录、搜索文件。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = FileOpsInput

    def _run(
        self,
        get_doc: bool = False,
        operation: str = "",
        file_path: str = "",
        content: str = "",
        new_path: str = "",
        directory_path: str = "",
        search_pattern: str = "",
        search_directory: str = ".",
        recursive: bool = False,
        file_filter: str = "all",
        extension: str = "",
    ) -> str:
        if get_doc:
            return self._load_doc()
        if not operation:
            return format_error("operation 不能为空")

        try:
            if operation == "read_file":
                return self._read_file(file_path)
            elif operation == "write_file":
                return self._write_file(file_path, content)
            elif operation == "delete_file":
                return self._delete_file(file_path)
            elif operation == "rename_file":
                return self._rename_file(file_path, new_path)
            elif operation == "create_directory":
                return self._create_directory(directory_path)
            elif operation == "list_directory":
                return self._list_directory(directory_path)
            elif operation == "search_files":
                return self._search_files(search_pattern, search_directory, recursive, file_filter, extension)
            else:
                return format_error(f"未知的操作类型: {operation}")
        except Exception as e:
            return format_error(str(e))

    def _read_file(self, file_path: str) -> str:
        if not file_path:
            return format_error("读取文件需要提供 file_path")
        if not os.path.exists(file_path):
            return format_error(f"文件不存在: {file_path}")
        if not os.path.isfile(file_path):
            return format_error(f"路径不是文件: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            data = f.read()

        st = os.stat(file_path)
        return format_success({
            "content": data,
            "file_info": {
                "size": st.st_size,
                "path": os.path.abspath(file_path),
            },
        })

    def _write_file(self, file_path: str, content: str) -> str:
        if not file_path:
            return format_error("写入文件需要提供 file_path")
        if not content:
            return format_error("写入文件需要提供 content")

        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return format_success({
            "message": f"文件已写入: {file_path}",
            "file_path": os.path.abspath(file_path),
            "size": len(content),
        })

    def _delete_file(self, file_path: str) -> str:
        if not file_path:
            return format_error("删除文件需要提供 file_path")
        if not os.path.exists(file_path):
            return format_error(f"文件不存在: {file_path}")

        if os.path.isfile(file_path):
            os.remove(file_path)
        elif os.path.isdir(file_path):
            shutil.rmtree(file_path)
        else:
            return format_error(f"未知的文件类型: {file_path}")

        return format_success({"message": f"已删除: {file_path}", "file_path": file_path})

    def _rename_file(self, file_path: str, new_path: str) -> str:
        if not file_path:
            return format_error("重命名需要提供 file_path")
        if not new_path:
            return format_error("重命名需要提供 new_path")
        if not os.path.exists(file_path):
            return format_error(f"文件不存在: {file_path}")
        if os.path.exists(new_path):
            return format_error(f"目标已存在: {new_path}")

        os.rename(file_path, new_path)
        return format_success({
            "message": f"已重命名: {file_path} → {new_path}",
            "old_path": file_path,
            "new_path": new_path,
        })

    def _create_directory(self, directory_path: str) -> str:
        if not directory_path:
            return format_error("创建目录需要提供 directory_path")

        os.makedirs(directory_path, exist_ok=True)
        return format_success({
            "message": f"目录已创建: {directory_path}",
            "directory_path": os.path.abspath(directory_path),
        })

    def _list_directory(self, directory_path: str) -> str:
        if not directory_path:
            directory_path = "."
        if not os.path.exists(directory_path):
            return format_error(f"目录不存在: {directory_path}")
        if not os.path.isdir(directory_path):
            return format_error(f"路径不是目录: {directory_path}")

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

    def _search_files(self, pattern: str, directory: str, recursive: bool, file_filter: str, extension: str) -> str:
        if not pattern:
            pattern = "*"
        if not directory:
            directory = "."
        if not os.path.exists(directory):
            return format_error(f"搜索目录不存在: {directory}")

        search_path = os.path.join(directory, "**", pattern) if recursive else os.path.join(directory, pattern)
        found = []
        for fp in glob.glob(search_path, recursive=recursive):
            if file_filter == "files_only" and not os.path.isfile(fp):
                continue
            if file_filter == "directories_only" and not os.path.isdir(fp):
                continue
            if file_filter == "by_extension" and extension and not fp.lower().endswith(extension.lower()):
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
