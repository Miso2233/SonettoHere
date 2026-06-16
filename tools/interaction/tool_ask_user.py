"""Tool: ask_user_for_info — 向用户询问信息。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success


class AskUserInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    question: str = Field(default="", description="需要询问用户的问题")


class AskUserTool(ToolBase):
    name: str = "ask_user_for_info"
    description: str = (
        "向用户询问信息并等待回复。用于需要确认或补充信息的场景。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = AskUserInput

    def _run(self, get_doc: bool = False, question: str = "") -> str:
        if get_doc:
            return self._load_doc()
        if not question:
            return format_error("question 不能为空")

        try:
            answer = input(question)
            return format_success({"question": question, "answer": answer})
        except EOFError:
            return format_error("无法获取用户输入（非交互模式）")
