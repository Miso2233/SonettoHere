"""Tool: answer_book — 答案之书（随机神秘答案）。"""

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success


class AnswerBookInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明")
    question: str = Field(default="", description="你想要提问的问题")


class AnswerBookTool(ToolBase):
    name: str = "answer_book"
    description: str = (
        "答案之书：提出一个问题，获得随机神秘答案。仅供娱乐参考。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = AnswerBookInput

    def _run(self, get_doc: bool = False, question: str = "") -> str:
        if get_doc:
            return self._load_doc()
        if not question:
            return format_error("问题不能为空")

        try:
            result = self.client.uapi.random.get_answerbook_ask(question=question)
            return format_success(result)
        except Exception as e:
            return format_error(f"答案之书查询失败: {e}")
