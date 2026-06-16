"""Tool: create_memory — 添加一条新记忆条目。"""

from pathlib import Path

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success


class CreateMemoryInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    content: str = Field(default="", description="记忆内容，用第三人称中文描述用户的一个事实")
    section: str = Field(default="", description="记忆分区，如「身份」「音乐」「品味」「地点与路径」「瞬间」「时效待办」，也可创建新分区（1-4字中文名词）")


MEMORY_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "personas" / "memory.yaml"


class CreateMemoryTool(ToolBase):
    name: str = "create_memory"
    description: str = (
        "添加一条新的长期记忆条目到指定分区。返回该条目的唯一 ID。"
        "[调用积极性: 仅在用户引用或提及时调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = CreateMemoryInput

    def _run(self, get_doc: bool = False, content: str = "", section: str = "") -> str:
        if get_doc:
            return self._load_doc()

        if not content:
            return format_error("content 不能为空，请提供记忆内容")
        if not section:
            return format_error("section 不能为空，请指定记忆分区")

        from memory.memory_manager import MemoryManager

        mm = MemoryManager(yaml_file=str(MEMORY_PATH))
        new_id = mm.add(description=content, theme=section)
        return format_success({
            "id": new_id,
            "content": content,
            "section": section,
            "message": f"已创建 [{new_id}] ({section}): {content}",
        })
