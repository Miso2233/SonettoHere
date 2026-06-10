"""Skill: list_memories — 列出所有记忆条目（每条截断以节省上下文）。"""

from pathlib import Path

from pydantic import BaseModel, Field

from skills.base import SkillBase, format_success


class ListMemoriesInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")


MEMORY_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "personas" / "memory.yaml"

# 描述截断长度（字符数），取自现有 memory.yaml 描述长度分布分析
# 大部分描述在 100-300 字符，200 字能覆盖关键信息，节省约 40% 上下文
TRUNCATE_LEN = 200


def _truncate(text: str) -> str:
    """超出 TRUNCATE_LEN 的描述截断并追加 …。"""
    if len(text) <= TRUNCATE_LEN:
        return text
    return text[:TRUNCATE_LEN] + "…"


def _format_entries(items: list[dict]) -> str:
    """按 theme 分组格式化记忆条目（已截断）。"""
    if not items:
        return "（暂无记忆条目）"
    by_theme: dict[str, list[dict]] = {}
    theme_order: list[str] = []
    for item in items:
        theme = item["theme"]
        by_theme.setdefault(theme, []).append(item)
        if theme not in theme_order:
            theme_order.append(theme)
    lines = []
    for theme in theme_order:
        lines.append(f"## {theme}")
        for item in by_theme[theme]:
            desc = _truncate(item["description"])
            lines.append(f"  [{item['id']}] {desc}")
        lines.append("")
    return "\n".join(lines).strip()


class ListMemoriesSkill(SkillBase):
    name: str = "list_memories"
    description: str = (
        "查看所有长期记忆条目的概览列表（每条描述已截断以节省上下文）。"
        "如需读取某条记忆的完整内容，再调用 read_memories 传入其 ID。"
        "★ 首次使用先 get_doc=true 阅读完整说明。"
    )
    args_schema: type[BaseModel] = ListMemoriesInput

    def _run(self, get_doc: bool = False) -> str:
        if get_doc:
            return self._load_doc()

        if not MEMORY_PATH.exists():
            return format_success({"items": [], "formatted": "（暂无记忆条目）"})

        from memory.memory_manager import MemoryManager

        mm = MemoryManager(yaml_file=str(MEMORY_PATH))
        items = mm.show()

        # 返回 items 时同样截断，供前端气泡使用
        truncated_items = [
            {**item, "description": _truncate(item["description"])}
            for item in items
        ]
        formatted = _format_entries(items)
        return format_success({
            "count": len(items),
            "items": truncated_items,
            "formatted": formatted,
        })
