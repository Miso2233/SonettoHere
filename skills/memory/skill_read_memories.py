"""Skill: read_memories — 查看所有记忆条目。"""

from pathlib import Path

from pydantic import BaseModel, Field

from skills.base import SkillBase, format_success


class ReadMemoriesInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")


MEMORY_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "personas" / "memory.yaml"


def _format_entries(items: list[dict]) -> str:
    """按 theme 分组格式化记忆条目。"""
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
            lines.append(f"  [{item['id']}] {item['description']}")
        lines.append("")
    return "\n".join(lines).strip()


class ReadMemoriesSkill(SkillBase):
    name: str = "read_memories"
    description: str = (
        "查看当前所有长期记忆条目及其 ID 和分区。"
        "在增删改查记忆之前必须先调用此工具了解现有条目。"
        "★ 首次使用先 get_doc=true 阅读完整说明。"
    )
    args_schema: type[BaseModel] = ReadMemoriesInput

    def _run(self, get_doc: bool = False) -> str:
        if get_doc:
            return self._load_doc()

        if not MEMORY_PATH.exists():
            return format_success({"items": [], "formatted": "（暂无记忆条目）"})

        from memory.memory_manager import MemoryManager

        mm = MemoryManager(yaml_file=str(MEMORY_PATH))
        items = mm.show()
        formatted = _format_entries(items)
        return format_success({
            "count": len(items),
            "items": items,
            "formatted": formatted,
        })
