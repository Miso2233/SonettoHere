"""Tool: file_edit — 文件多笔精确编辑（基于 Claude Code Edit 工具模式）。

edits 传入 JSON 数组，单笔替换同样放入数组；每笔按顺序执行，
old_string 必须与文件内容完全一致（含空白、缩进），不唯一时报错或开启 replace_all。
执行前需用户确认放行。
"""

import json
import os
from typing import Any

from pydantic import BaseModel, Field

from tools.base import (
    ToolBase,
    check_path_whitelisted,
    check_sonetto_blocker,
    format_error,
    format_success,
)
from tools.confirm import confirm_execution


class FileEditInput(BaseModel):
    file_path: str = Field(default="", description="文件绝对路径")
    edits: str = Field(
        default="",
        description=(
            '编辑列表 JSON 数组，每笔: {"old_string": "...", "new_string": "...", '
            '"replace_all": false}。单笔替换也需放入数组中。'
        ),
    )


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

    def _run(self, file_path: str = "", edits: str = "") -> str:
        raise NotImplementedError("file_edit 仅支持异步模式，请使用 _arun")

    async def _arun(self, file_path: str = "", edits: str = "") -> str:
        """用户确认放行后：校验并执行多笔精确编辑。"""
        if not file_path:
            return format_error("file_path 不能为空")

        blocked = check_sonetto_blocker(file_path)
        if blocked:
            return format_error(
                "🚫 安全阻断：操作已被 SonettoBlocker 阻断。\n"
                f'在目录 "{blocked}" 中发现了 SonettoBlocker 文件。\n\n'
                "请立即停止当前任务，先说明你为什么需要访问该路径，"
                "再说明下一步打算做什么。"
            )

        blocked = check_path_whitelisted(file_path)
        if blocked:
            return format_error(blocked)

        if not os.path.exists(file_path):
            return format_error(f"文件不存在: {file_path}")
        if not os.path.isfile(file_path):
            return format_error(f"不是文件: {file_path}")

        try:
            return self._edit(file_path, edits)
        except OSError as e:
            return format_error(str(e))

    def _edit(self, file_path: str, edits_json: str) -> str:
        if not edits_json:
            return format_error("file_edit 需要提供 edits（JSON 数组）")

        try:
            edit_list = json.loads(edits_json)
        except (json.JSONDecodeError, TypeError) as e:
            return format_error(f"edits JSON 解析失败: {e}")

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
