"""Tool: file_search_text — 在文件内容中进行正则文本搜索。"""

import os
import re
from typing import Any

from pydantic import BaseModel, Field

from tools.background import background
from tools.base import (
    ToolBase,
    format_error,
    format_success,
    off_thread,
)
from tools.path_guard import PathSpec, path_guard


class FileSearchTextInput(BaseModel):
    file_path: str = Field(default="", description="文件绝对路径")
    pattern: str = Field(default="", description="搜索模式（支持正则）")
    case_insensitive: bool = Field(default=False, description="搜索时是否忽略大小写")


@path_guard(PathSpec("file_path", kind="file"))
@background
class FileSearchTextTool(ToolBase):
    name: str = "file_search_text"
    description: str = (
        "在单个文件内容中进行正则文本搜索，返回每处匹配的行号、列号与匹配文本。"
        "[调用积极性: 可自由看情况调用]"
    )
    args_schema: type[BaseModel] = FileSearchTextInput

    async def _arun(
        self,
        file_path: str = "",
        pattern: str = "",
        case_insensitive: bool = False,
    ) -> str:
        return await off_thread(self._run_impl, file_path, pattern, case_insensitive)

    def _run_impl(
        self,
        file_path: str = "",
        pattern: str = "",
        case_insensitive: bool = False,
    ) -> str:
        if not pattern:
            return format_error("search 需要提供 pattern")

        flags = re.MULTILINE
        if case_insensitive:
            flags |= re.IGNORECASE

        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return format_error(f"正则表达式错误: {e}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            return format_error(
                f"文件编码错误: 文件 '{file_path}' 不是有效的 UTF-8 编码，"
                "无法以文本方式读取。请确认文件编码或以二进制方式处理。"
            )

        matches: list[dict[str, Any]] = []
        for i, line in enumerate(lines):
            for m in regex.finditer(line.rstrip("\n\r")):
                matches.append(
                    {
                        "line_num": i + 1,
                        "column": m.start() + 1,
                        "match": m.group(),
                    }
                )

        return format_success(
            {
                "file_path": os.path.abspath(file_path),
                "pattern": pattern,
                "total_matches": len(matches),
                "matches": matches,
            }
        )
