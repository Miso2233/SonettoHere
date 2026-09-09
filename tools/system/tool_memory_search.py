"""Tool: memory_search — 主 Agent 长期记忆精确搜索（主题 + 正则 + related 多级关联）。"""

import re

import yaml
from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success, off_thread


class MemorySearchInput(BaseModel):
    regex: str = Field(
        description="用于在记忆 description 上执行 re.search 的正则表达式（必填）"
    )
    theme: str | None = Field(
        default=None,
        description=(
            "可选：限定某一主题 KEY（USER/PREFERENCE/PROJECT/PATH/LOCATION/"
            "TODO/TECH/SELF/MOMENT）；不填则搜索全部主题"
        ),
    )


class MemorySearchTool(ToolBase):
    name: str = "memory_search"
    description: str = (
        "在长期记忆中精确搜索：先用可选主题 KEY + 必填正则匹配记忆内容，"
        "再沿记忆的 related（无向关联）推出命中条目的全部多级关联条目并一起返回。"
        "只读工具，不会修改记忆。长期记忆不会自动注入对话——需要了解用户的过往对话、"
        "偏好或此前聊过的话题且本轮上下文缺少依据时，应主动调用本工具检索；"
        "若一次无结果，可放宽关键词或更换正则再试。"
        "[调用积极性: 当回答依赖用户过往信息时主动调用]"
    )
    args_schema: type[BaseModel] = MemorySearchInput

    async def _arun(self, regex: str = "", theme: str | None = None) -> str:
        return await off_thread(self._run_impl, regex, theme)

    def _run_impl(self, regex: str = "", theme: str | None = None) -> str:
        from api.memory import search as memory_search
        from api.memory.long_term import MEMORY_PATH
        from api.memory.manager import YamlMemoryManager

        def _empty(summary: str) -> str:
            return format_success({
                "summary": summary, "theme": theme, "regex": regex,
                "matched_total": 0, "matched": [],
                "related_total": 0, "related": [], "truncated": False,
            })

        if not MEMORY_PATH.exists():
            return _empty("（暂无长期记忆）")
        try:
            manager = YamlMemoryManager(yaml_file=str(MEMORY_PATH))
            adjacency = memory_search.collect_adjacency(manager)
            result = memory_search.search_with_closure(
                adjacency, theme=theme, regex=regex
            )
        except re.error as e:
            return format_error(f"正则表达式错误: {e}")
        except ValueError as e:
            return format_error(f"{e}")
        except (OSError, TypeError, yaml.YAMLError):
            return format_error("记忆库暂不可读，请稍后重试。")

        matched = [
            {"id": m["id"], "theme": m["theme"], "description": m["description"]}
            for m in result.get("matched", [])
        ]
        related = [
            {
                "id": m["id"], "theme": m["theme"], "description": m["description"],
                "depth": m.get("depth", 1),
            }
            for m in result.get("related", [])
        ]
        matched_total = len(matched)
        related_total = result.get("related_total", 0)
        truncated = result.get("truncated", False)

        if matched_total == 0 and related_total == 0:
            summary = "（无匹配记忆）"
        else:
            parts = [f"命中 {matched_total} 条"]
            if related_total:
                parts.append(f"关联 {related_total} 条")
            if truncated:
                parts.append("超出展示上限已截断")
            summary = "，".join(parts)

        return format_success({
            "summary": summary, "theme": theme, "regex": regex,
            "matched_total": matched_total, "matched": matched,
            "related_total": related_total, "related": related,
            "truncated": truncated,
        })
