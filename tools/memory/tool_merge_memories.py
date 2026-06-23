"""Tool: merge_memories — 合并两条相似记忆。"""

from pathlib import Path

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success
from memory.memory_manager import MAX_DESC_LENGTH


class MergeMemoriesInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    id1: str = Field(default="", description="合并后保留的记忆 ID（主条目）")
    id2: str = Field(default="", description="合并后将被删除的记忆 ID（从条目）")
    content: str = Field(
        default="", description="合并后的完整记忆内容，涵盖两条原条目的信息"
    )
    section: str = Field(default="", description="合并后的记忆分区")
    reason: str = Field(
        default="", description="合并原因，说明为什么这两条记忆需要合并"
    )


MEMORY_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "config"
    / "personas"
    / "memory.yaml"
)


class MergeMemoriesTool(ToolBase):
    name: str = "merge_memories"
    description: str = (
        "将两条相似记忆合并为一条，id1 保留、id2 被删除，同时保留两者的修改历史。"
        "当两条记忆描述同一事物（如分散的身份信息、同一首歌在不同分区的重复条目）时使用，避免碎片化。"
        "[调用积极性: 绝对不要在用户没有提及该工具名时使用|仅在用户引用或提及时调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = MergeMemoriesInput

    def _run(
        self,
        get_doc: bool = False,
        id1: str = "",
        id2: str = "",
        content: str = "",
        section: str = "",
        reason: str = "",
    ) -> str:
        if get_doc:
            return self._load_doc()

        if not id1:
            return format_error("id1 不能为空，请提供要保留的主条目 ID")
        if not id2:
            return format_error("id2 不能为空，请提供要合并的从条目 ID")
        if not content:
            return format_error("content 不能为空，请提供合并后的内容")
        if len(content) > MAX_DESC_LENGTH:
            return format_error(
                f"合并后的记忆内容超过 {MAX_DESC_LENGTH} 字限制（当前 {len(content)} 字），"
                f"请精简至 {MAX_DESC_LENGTH} 字以内，或保留两条各自独立"
            )
        if not section:
            return format_error("section 不能为空，请指定合并后的分区")
        if not reason:
            return format_error("reason 不能为空，请说明合并原因")

        from memory.memory_manager import MemoryManager

        mm = MemoryManager(yaml_file=str(MEMORY_PATH))
        try:
            mm.merge(id1, id2, content, section, reason)
        except ValueError:
            return format_error(
                f"未找到 ID 为 {id1} 或 {id2} 的记忆条目。请先调用 read_memories 确认 ID。"
            )
        return format_success(
            {
                "kept_id": id1,
                "removed_id": id2,
                "content": content,
                "section": section,
                "reason": reason,
                "message": f"已合并 [{id2}] → [{id1}] ({section}): {content}",
            }
        )
