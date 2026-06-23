"""Tool: update_memory — 更新已有记忆条目。"""

from pathlib import Path

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success
from memory.memory_manager import MAX_DESC_LENGTH


class UpdateMemoryInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    id: str = Field(
        default="", description="要更新的记忆 ID（来自 read_memories 的输出）"
    )
    content: str = Field(default="", description="更新后的完整记忆内容")
    reason: str = Field(default="", description="修改原因，说明为什么要更新这条记忆")


MEMORY_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "config"
    / "personas"
    / "memory.yaml"
)


class UpdateMemoryTool(ToolBase):
    name: str = "update_memory"
    description: str = (
        "根据 ID 更新一条已有长期记忆的内容。"
        "[调用积极性: 绝对不要在用户没有提及该工具名时使用|仅在用户引用或提及时调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = UpdateMemoryInput

    def _run(
        self, get_doc: bool = False, id: str = "", content: str = "", reason: str = ""
    ) -> str:
        if get_doc:
            return self._load_doc()

        if not id:
            return format_error("id 不能为空，请提供要更新的记忆 ID")
        if not content:
            return format_error("content 不能为空，请提供更新后的内容")
        if len(content) > MAX_DESC_LENGTH:
            return format_error(
                f"更新后的记忆内容超过 {MAX_DESC_LENGTH} 字限制（当前 {len(content)} 字），"
                f"请精简至 {MAX_DESC_LENGTH} 字以内，或拆分为多条独立条目"
            )
        if not reason:
            return format_error("reason 不能为空，请说明更新原因")

        from memory.memory_manager import MemoryManager

        mm = MemoryManager(yaml_file=str(MEMORY_PATH))
        try:
            mm.update(id, reason=reason, new_description=content)
        except ValueError:
            return format_error(
                f"未找到 ID 为 {id} 的记忆条目。请先调用 read_memories 确认 ID。"
            )
        return format_success(
            {
                "id": id,
                "content": content,
                "reason": reason,
                "message": f"已更新 [{id}]: {content}",
            }
        )
