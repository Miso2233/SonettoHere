"""Tool: ask_user_multi_choice — 向用户提供多项选择，用户可选多项。"""

import asyncio

from pydantic import BaseModel, Field

from api.agent import interaction
from api.events import ToolSender
from tools.base import ToolBase, format_error, format_success

# 前端自定义文本输入的前缀标记，用于区分「选中的选项」和「用户手写输入」
_CUSTOM_PREFIX = "__custom__::"


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
            data: dict = {
                "question": question,
                "answer": answer,
                "options": options,
            }
            # 检测用户是否通过「告诉Sonetto别的意见」提交了自定义文本
            if isinstance(answer, list):
                cleaned: list[str] = []
                has_custom = False
                for item in answer:
                    if isinstance(item, str) and item.startswith(_CUSTOM_PREFIX):
                        cleaned.append(item[len(_CUSTOM_PREFIX):])
                        has_custom = True
                    else:
                        cleaned.append(item)
                data["answer"] = cleaned
                if has_custom:
                    data["is_custom_text"] = True
            elif isinstance(answer, str) and answer.startswith(_CUSTOM_PREFIX):
                data["answer"] = answer[len(_CUSTOM_PREFIX):]
                data["is_custom_text"] = True
            return format_success(data)
        except asyncio.CancelledError:
            return format_error("用户取消了回复")
        finally:
            interaction.cleanup(interaction_id)
