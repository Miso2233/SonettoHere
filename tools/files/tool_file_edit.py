"""Tool: file_edit — 文件精确编辑工具（基于 Claude Code Edit 工具模式）。"""

import json
import os
import re
from typing import Any

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success


class FileEditInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明和领域知识")

    operation: str = Field(
        default="",
        description="操作类型: edit / multi_edit / read / search",
    )
    file_path: str = Field(default="", description="文件绝对路径")

    # edit 操作
    old_string: str = Field(default="", description="要被替换掉的原文，必须完全一致（含空白、缩排、换行）")
    new_string: str = Field(default="", description="替换后的新内容")
    replace_all: bool = Field(default=False, description="设为 true 则替换文件中所有匹配项")

    # multi_edit 操作
    edits: str = Field(
        default="",
        description="multi_edit 操作的 JSON 编辑列表，格式: [{\"old_string\": \"...\", \"new_string\": \"...\", \"replace_all\": false}]",
    )

    # read 操作
    offset: int = Field(default=0, description="读取起始行号（0 表示从头）")
    limit: int = Field(default=0, description="读取行数（0 表示全部）")

    # search 操作
    pattern: str = Field(default="", description="搜索模式（支持正则）")
    case_insensitive: bool = Field(default=False, description="搜索时是否忽略大小写")


class FileEditTool(ToolBase):
    name: str = "file_edit"
    description: str = (
        "文件精确编辑：读取文件、精确字符串替换、多笔编辑、文本搜索。"
        "基于 Claude Code Edit 工具模式，支持 old_string 精确匹配替换。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = FileEditInput

    def _run(
        self,
        get_doc: bool = False,
        operation: str = "",
        file_path: str = "",
        old_string: str = "",
        new_string: str = "",
        replace_all: bool = False,
        edits: str = "",
        offset: int = 0,
        limit: int = 0,
        pattern: str = "",
        case_insensitive: bool = False,
    ) -> str:
        if get_doc:
            return self._load_doc()

        if not operation:
            return format_error("operation 必填: edit / multi_edit / read / search")
        if not file_path:
            return format_error("file_path 不能为空")
        if not os.path.exists(file_path):
            return format_error(f"文件不存在: {file_path}")
        if not os.path.isfile(file_path):
            return format_error(f"不是文件: {file_path}")

        try:
            if operation == "read":
                return self._read(file_path, offset, limit)
            elif operation == "edit":
                return self._edit(file_path, old_string, new_string, replace_all)
            elif operation == "multi_edit":
                return self._multi_edit(file_path, edits)
            elif operation == "search":
                return self._search(file_path, pattern, case_insensitive)
            else:
                return format_error(f"未知操作: {operation}")
        except Exception as e:
            return format_error(str(e))

    # ── Read ──────────────────────────────────────────────────────

    def _read(self, file_path: str, offset: int = 0, limit: int = 0) -> str:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        total_lines = len(lines)
        start = offset if offset > 0 else 0
        end = start + limit if limit > 0 else total_lines
        selected = lines[start:end]

        return format_success({
            "file_path": os.path.abspath(file_path),
            "total_lines": total_lines,
            "offset": start,
            "limit": end - start,
            "lines": [
                {"num": start + i + 1, "content": line.rstrip("\n\r")}
                for i, line in enumerate(selected)
            ],
            "content": "".join(selected),
        })

    # ── Edit ──────────────────────────────────────────────────────

    def _edit(
        self, file_path: str, old_string: str, new_string: str, replace_all: bool = False
    ) -> str:
        if not old_string:
            return format_error("edit 操作需要提供 old_string")
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        count = content.count(old_string)
        if count == 0:
            return format_error("未找到匹配的 old_string，内容不匹配")
        if count > 1 and not replace_all:
            return format_error(
                f"old_string 有 {count} 处匹配。请提供更多上下文使匹配唯一，"
                f"或设置 replace_all=true 替换全部"
            )

        new_content = content.replace(old_string, new_string, -1 if replace_all else 1)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return format_success({
            "file_path": os.path.abspath(file_path),
            "replaced_count": count if replace_all else 1,
            "replace_all": replace_all,
            "total_lines": new_content.count("\n") + 1,
            "message": f"已替换 {count if replace_all else 1} 处匹配",
        })

    # ── Multi-Edit ───────────────────────────────────────────────

    def _multi_edit(self, file_path: str, edits_json: str) -> str:
        if not edits_json:
            return format_error("multi_edit 操作需要提供 edits（JSON 字符串）")

        try:
            edit_list = json.loads(edits_json)
        except (json.JSONDecodeError, TypeError) as e:
            return format_error(f"edits JSON 解析失败: {e}")

        if not isinstance(edit_list, list) or not edit_list:
            return format_error("edits 应为非空 JSON 数组")

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        results: list[dict[str, Any]] = []
        for i, edit in enumerate(edit_list):
            old = edit.get("old_string", "")
            new = edit.get("new_string", "")
            all_ = edit.get("replace_all", False)

            if not old:
                results.append({"index": i, "status": "error", "message": "old_string 为空"})
                continue

            count = content.count(old)
            if count == 0:
                results.append({"index": i, "status": "error", "message": "未找到匹配"})
                continue
            if count > 1 and not all_:
                results.append({
                    "index": i, "status": "error",
                    "message": f"有 {count} 处匹配，需设置 replace_all=true",
                })
                continue

            content = content.replace(old, new, -1 if all_ else 1)
            results.append({"index": i, "status": "ok", "replaced_count": count if all_ else 1})

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        success_count = sum(1 for r in results if r["status"] == "ok")
        return format_success({
            "file_path": os.path.abspath(file_path),
            "total_edits": len(edit_list),
            "success_count": success_count,
            "failed_count": len(edit_list) - success_count,
            "results": results,
        })

    # ── Search ───────────────────────────────────────────────────

    def _search(self, file_path: str, pattern: str, case_insensitive: bool = False) -> str:
        if not pattern:
            return format_error("search 操作需要提供 pattern")

        flags = re.MULTILINE
        if case_insensitive:
            flags |= re.IGNORECASE

        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return format_error(f"正则表达式错误: {e}")

        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        matches: list[dict[str, Any]] = []
        for i, line in enumerate(lines):
            for m in regex.finditer(line.rstrip("\n\r")):
                matches.append({
                    "line_num": i + 1,
                    "column": m.start() + 1,
                    "match": m.group(),
                })

        return format_success({
            "file_path": os.path.abspath(file_path),
            "pattern": pattern,
            "total_matches": len(matches),
            "matches": matches,
        })
