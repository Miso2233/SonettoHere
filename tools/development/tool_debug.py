"""Tool: debugger — Python 代码调试/变量检查/异常捕获。"""

import traceback

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success


class DebuggerInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明和领域知识")
    code: str = Field(default="", description="需要调试/执行的 Python 代码")
    variables: list[str] = Field(default_factory=list, description="需要监视的变量名列表")


class DebuggerTool(ToolBase):
    name: str = "debugger"
    description: str = (
        "在隔离环境中执行 Python 代码并检查变量值、捕获异常和堆栈跟踪。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = DebuggerInput

    def _run(
        self,
        get_doc: bool = False,
        code: str = "",
        variables: list[str] | None = None,
    ) -> str:
        if get_doc:
            return self._load_doc()
        if not code:
            return format_error("code 不能为空")

        if variables is None:
            variables = []

        env: dict = {}
        try:
            exec(code, {"__builtins__": __builtins__}, env)
            return format_success({
                "status": "success",
                "variables": {v: repr(env.get(v, "未定义")) for v in variables},
                "output": "代码执行成功",
            })
        except Exception as e:
            return format_success({
                "status": "error",
                "error_type": type(e).__name__,
                "error_message": str(e),
                "traceback": traceback.format_exc(),
                "variables": {v: repr(env.get(v, "未定义")) for v in variables},
            })
