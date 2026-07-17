"""Tool: ask_user_multi_choice — 向用户提供多项选择，用户可选多项。"""

import asyncio

from pydantic import BaseModel, Field

from api.agent import interaction
from api.events import ToolSender
from tools.base import ToolBase, format_error, format_success


class AskUserMultiChoiceInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    question: str = Field(default="", description="需要询问用户的问题")
    options: list[str] = Field(default=[], description="选项列表，用户可勾选多项")


class AskUserMultiChoiceTool(ToolBase):
    name: str = "ask_user_multi_choice"
    description: str = (
        "向用户提供多个选项，用户可勾选多项。用于需要用户做多选的场景。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = AskUserMultiChoiceInput

    def _run(
        self,
        get_doc: bool = False,
        question: str = "",
        options: list[str] | None = None,
    ) -> str:
        raise NotImplementedError("ask_user_multi_choice 仅支持异步模式")

    async def _arun(
        self,
        get_doc: bool = False,
        question: str = "",
        options: list[str] | None = None,
    ) -> str:
        if get_doc:
            return self._load_doc()
        if not question:
            return format_error("question 不能为空")
        if not options:
            return format_error("options 不能为空")

        sender = ToolSender.from_context()
        if sender is None:
            return format_error("WebSocket 连接不可用")

        interaction_id, future = interaction.register()

        await sender.ask_user(self.name, question, "multi_choice", options, interaction_id)

        try:
            answer = await future
            return format_success(
                {"question": question, "answer": answer, "options": options}
            )
        except asyncio.CancelledError:
            return format_error("用户取消了回复")
        finally:
            interaction.cleanup(interaction_id)
