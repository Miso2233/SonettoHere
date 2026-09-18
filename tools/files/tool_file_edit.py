"""Tool: file_edit — 文件多笔精确编辑（基于 Claude Code Edit 工具模式）。

edits 传入 JSON 数组，单笔替换同样放入数组；每笔按顺序执行，
old_string 必须与文件内容完全一致（含空白、缩进），不唯一时报错或开启 replace_all。
执行前需用户确认放行。
"""

import json
import os
from typing import Any

from pydantic import BaseModel, Field, field_validator

from tools.base import (
    ToolBase,
    format_error,
    format_success,
    off_thread,
)
from tools.confirm import confirm_execution
from tools.path_guard import PathSpec, path_guard


class FileEditInput(BaseModel):
    file_path: str = Field(default="", description="文件绝对路径")
    edits: str = Field(
        default="",
        description=(
            '编辑列表 JSON 数组，每笔: {"old_string": "...", "new_string": "...", '
            '"replace_all": false}。单笔替换也需放入数组中。'
        ),
    )

    @field_validator("edits", mode="before")
    @classmethod
    def _coerce_edits(cls, value: Any) -> Any:
        """edits 同时接受 JSON 数组文本、已解析的数组与单笔编辑对象。

        上游调用链若已把数组解析成 ``list``（或把单笔编辑直接下发成 ``dict``），
        这里统一序列化回文本，由 ``_edit`` 走 ``json.loads`` 解析路径，避免
        "Input should be a valid string" 之类的校验失败。
        """
        if isinstance(value, dict):
            value = [value]
        if isinstance(value, (list, tuple)):
            return json.dumps(list(value), ensure_ascii=False)
        return value


@path_guard(PathSpec("file_path", kind="file"))
@confirm_execution(
    question="即将对文件应用编辑，是否确认执行？",
    approve_text="允许编辑",
    reject_text="拒绝",
    reject_message="用户拒绝编辑文件",
)
class FileEditTool(ToolBase):
    name: str = "file_edit"
    description: str = (
        "对文件进行多笔精确字符串替换（单笔也传入数组）。edits 为 JSON 数组，"
        "old_string 必须与文件内容完全一致（含空白、缩进），不唯一时需设置 replace_all。"
        "仅支持 UTF-8 编码的文本文件。"
        "[调用积极性: 可自由看情况调用]"
    )
    args_schema: type[BaseModel] = FileEditInput

    async def _arun(self, file_path: str = "", edits: str = "") -> str:
        """用户确认放行后：离环执行校验与编辑。"""
        return await off_thread(self._run_impl, file_path, edits)

    def _run_impl(self, file_path: str = "", edits: str = "") -> str:
        """执行多笔精确编辑（路径校验由 @path_guard 承接）。"""
        try:
            return self._edit(file_path, edits)
        except OSError as e:
            return format_error(str(e))

    def _edit(self, file_path: str, edits_json: str) -> str:
        if not edits_json:
            return format_error("file_edit 需要提供 edits（JSON 数组）")

        # 兜底：绕过 args_schema 直接调用时，允许传入已解析的列表 / 单笔编辑对象
        if isinstance(edits_json, dict):
            edit_list: Any = [edits_json]
        elif isinstance(edits_json, (list, tuple)):
            edit_list = list(edits_json)
        else:
            try:
                edit_list = json.loads(edits_json)
            except (json.JSONDecodeError, TypeError) as e:
                return format_error(f"edits JSON 解析失败: {e}")

        # JSON 对象文本（单笔编辑忘了包数组）同样按单笔处理，与 schema 层一致
        if isinstance(edit_list, dict):
            edit_list = [edit_list]

        if not isinstance(edit_list, list) or not edit_list:
            return format_error("edits 应为非空 JSON 数组")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            return format_error(
                f"文件编码错误: 文件 '{file_path}' 不是有效的 UTF-8 编码，"
                "无法以文本方式读取。请确认文件编码或以二进制方式处理。"
            )

        results: list[dict[str, Any]] = []
        for i, edit in enumerate(edit_list):
            old = edit.get("old_string", "")
            new = edit.get("new_string", "")
            all_ = edit.get("replace_all", False)

            if not old:
                results.append(
                    {"index": i, "status": "error", "message": "old_string 为空"}
                )
                continue

            count = content.count(old)
            if count == 0:
                results.append({"index": i, "status": "error", "message": "未找到匹配"})
                continue
            if count > 1 and not all_:
                results.append(
                    {
                        "index": i,
                        "status": "error",
                        "message": f"有 {count} 处匹配，需设置 replace_all=true",
                    }
                )
                continue

            content = content.replace(old, new, -1 if all_ else 1)
            results.append(
                {"index": i, "status": "ok", "replaced_count": count if all_ else 1}
            )

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        success_count = sum(1 for r in results if r["status"] == "ok")
        return format_success(
            {
                "file_path": os.path.abspath(file_path),
                "total_edits": len(edit_list),
                "success_count": success_count,
                "failed_count": len(edit_list) - success_count,
                "results": results,
            }
        )
