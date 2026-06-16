"""Tool: syntax_checker — 代码语法检查。"""

import ast
import os
import subprocess
import tempfile

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success


class SyntaxCheckerInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明和领域知识")
    code: str = Field(default="", description="需要检查的代码内容")
    language: str = Field(default="python", description="语言: python/javascript/typescript")
    file_path: str = Field(default="", description="代码文件路径（可选，优先于 code）")


class SyntaxCheckerTool(ToolBase):
    name: str = "syntax_checker"
    description: str = (
        "检查代码语法错误。支持 Python（ast.parse）和 JavaScript/TypeScript（node --check）。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = SyntaxCheckerInput

    def _run(
        self,
        get_doc: bool = False,
        code: str = "",
        language: str = "python",
        file_path: str = "",
    ) -> str:
        if get_doc:
            return self._load_doc()

        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    code = f.read()
            except Exception as e:
                return format_error(f"文件读取失败: {e}")

        if not code:
            return format_error("必须提供 code 或 file_path")

        try:
            if language == "python":
                return self._check_python(code)
            elif language in ("javascript", "typescript"):
                return self._check_javascript(code)
            else:
                return format_error(f"不支持的语言: {language}")
        except Exception as e:
            return format_error(f"语法检查失败: {e}")

    def _check_python(self, code: str) -> str:
        try:
            ast.parse(code)
            return format_success({"language": "python", "errors": [], "warnings": []})
        except SyntaxError as e:
            return format_success({
                "language": "python",
                "errors": [{"line": e.lineno, "column": e.offset, "message": e.msg, "type": "SyntaxError"}],
                "warnings": [],
            })

    def _check_javascript(self, code: str) -> str:
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", suffix=".js", delete=False
            ) as f:
                f.write(code)
                tmp = f.name

            result = subprocess.run(
                ["node", "--check", tmp],
                capture_output=True, text=True, timeout=10,
            )
            os.unlink(tmp)

            if result.returncode == 0:
                return format_success({"language": "javascript", "errors": [], "warnings": []})
            else:
                return format_success({
                    "language": "javascript",
                    "errors": [{"message": result.stderr.strip(), "type": "SyntaxError"}],
                    "warnings": [],
                })
        except FileNotFoundError:
            if tmp:
                os.unlink(tmp)
            return format_error("Node.js 未安装，无法检查 JS/TS 语法")
        except Exception as e:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)
            return format_error(f"JS 语法检查失败: {e}")
