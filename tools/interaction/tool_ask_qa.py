"""Tool: ask_user_qa — 向用户提问并等待自由文本回复。"""

import asyncio

from pydantic import BaseModel, Field

from api import interaction
from tools.base import ToolBase, format_error, format_success


class AskUserQAInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    question: str = Field(default="", description="需要询问用户的问题")


class AskUserQATool(ToolBase):
    name: str = "ask_user_qa"
    description: str = (
        "向用户提问并等待文字回复。用于需要用户自由输入信息的场景。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = AskUserQAInput

    def _run(self, get_doc: bool = False, question: str = "") -> str:
        raise NotImplementedError("ask_user_qa 仅支持异步模式")

    async def _arun(self, get_doc: bool = False, question: str = "") -> str:
        if get_doc:
            return self._load_doc()
        if not question:
            return format_error("question 不能为空")

        ws = interaction.current_ws.get()

        interaction_id, future = interaction.register()

        await ws.send_json({
            "type": "ask_user",
            "payload": {
                "tool_name": self.name,
                "question": question,
                "mode": "qa",
                "options": [],
                "interaction_id": interaction_id,
            },
        })

        try:
            answer = await future
            return format_success({"question": question, "answer": answer})
        except asyncio.CancelledError:
            return format_error("用户取消了回复")
        finally:
            interaction.cleanup(interaction_id)
