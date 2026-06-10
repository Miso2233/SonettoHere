"""Skill: read_memories — 按 ID 读取单条记忆的完整内容。"""

from pathlib import Path

from pydantic import BaseModel, Field

from skills.base import SkillBase, format_error, format_success


class ReadMemoriesInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    id: str = Field(default="", description="要读取的记忆 ID（来自 list_memories 的输出）")


MEMORY_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "personas" / "memory.yaml"


class ReadMemoriesSkill(SkillBase):
    name: str = "read_memories"
    description: str = (
        "根据 ID 读取一条长期记忆的完整内容（含变更历史）。"
        "先用 list_memories 获取概览和 ID，再用此工具查看全文。"
        "★ 首次使用先 get_doc=true 阅读完整说明。"
    )
    args_schema: type[BaseModel] = ReadMemoriesInput

    def _run(self, get_doc: bool = False, id: str = "") -> str:
        if get_doc:
            return self._load_doc()

        if not id:
            return format_error("请提供要读取的记忆 ID")

        if not MEMORY_PATH.exists():
            return format_error("记忆文件不存在")

        from memory.memory_manager import MemoryManager

        mm = MemoryManager(yaml_file=str(MEMORY_PATH))
        items = mm.show()

        # 查找匹配 ID 的条目
        target = None
        for item in items:
            if item["id"] == id:
                target = item
                break

        if target is None:
            return format_error(f"未找到 ID 为 {id} 的记忆条目。请先调用 list_memories 确认 ID。")

        result = {
            "id": target["id"],
            "description": target["description"],
            "theme": target["theme"],
        }

        # 读取变更历史
        try:
            history = mm.show_description_history(id)
            if len(history) > 1:
                result["history"] = history
                result["history_count"] = len(history)
        except ValueError:
            pass

        # 文本格式
        lines = [f"## {target['theme']}", f"  [{target['id']}] {target['description']}"]
        if result.get("history"):
            lines.append("")
            lines.append("### 变更历史")
            for h in result["history"]:
                lines.append(f"  - {h['time']}: {h['description'][:60]}{'…' if len(h['description']) > 60 else ''}")
        result["formatted"] = "\n".join(lines)

        return format_success(result)
