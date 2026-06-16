"""Tool: delete_memory — 删除一条记忆条目。"""

from pathlib import Path

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success


class DeleteMemoryInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    id: str = Field(default="", description="要删除的记忆 ID（来自 read_memories 的输出）")
    reason: str = Field(default="", description="删除原因，说明为什么要删除这条记忆")


MEMORY_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "personas" / "memory.yaml"


class DeleteMemoryTool(ToolBase):
    name: str = "delete_memory"
    description: str = (
        "根据 ID 删除一条长期记忆。"
        "[调用积极性: 仅在用户引用或提及时调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = DeleteMemoryInput

    def _run(self, get_doc: bool = False, id: str = "", reason: str = "") -> str:
        if get_doc:
            return self._load_doc()

        if not id:
            return format_error("id 不能为空，请提供要删除的记忆 ID")
        if not reason:
            return format_error("reason 不能为空，请说明删除原因")

        from memory.memory_manager import MemoryManager

        mm = MemoryManager(yaml_file=str(MEMORY_PATH))
        try:
            removed = mm.delete(id)
        except ValueError:
            return format_error(f"未找到 ID 为 {id} 的记忆条目。请先调用 read_memories 确认 ID。")
        return format_success({
            "id": id,
            "removed_content": removed,
            "reason": reason,
            "message": f"已删除 [{id}]: {removed}",
        })
