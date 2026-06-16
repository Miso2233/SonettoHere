"""Tool: code_quality_analyzer — Python 代码质量分析。"""

import ast

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success


class CodeQualityInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明和领域知识")
    code: str = Field(default="", description="需要分析的 Python 代码")
    file_path: str = Field(default="", description="代码文件路径（可选，优先于 code）")
    analysis_type: str = Field(default="all", description="分析类型: complexity/maintainability/duplication/all")


class CodeQualityTool(ToolBase):
    name: str = "code_quality_analyzer"
    description: str = (
        "分析 Python 代码质量：复杂度（函数/行数）、可维护性（注释率/命名规范）、重复代码检测。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = CodeQualityInput

    def _run(
        self,
        get_doc: bool = False,
        code: str = "",
        file_path: str = "",
        analysis_type: str = "all",
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
            result = {}
            if analysis_type in ("complexity", "all"):
                result["complexity"] = self._analyze_complexity(code)
            if analysis_type in ("maintainability", "all"):
                result["maintainability"] = self._analyze_maintainability(code)
            if analysis_type in ("duplication", "all"):
                result["duplication"] = self._analyze_duplication(code)
            return format_success(result)
        except Exception as e:
            return format_error(f"质量分析失败: {e}")

    def _analyze_complexity(self, code: str) -> dict:
        tree = ast.parse(code)
        functions = []

        class FuncVisitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                functions.append({"name": node.name, "line": node.lineno, "endline": node.end_lineno})
            def visit_AsyncFunctionDef(self, node):
                functions.append({"name": node.name, "line": node.lineno, "endline": node.end_lineno})

        FuncVisitor().visit(tree)

        total_lines = len(code.split("\n"))
        avg_len = 0
        if functions:
            total = sum(f.get("endline", 0) - f.get("line", 0) + 1 for f in functions)
            avg_len = total / len(functions)

        return {"total_lines": total_lines, "function_count": len(functions), "avg_function_length": avg_len, "functions": functions}

    def _analyze_maintainability(self, code: str) -> dict:
        lines = code.split("\n")
        comment_lines = sum(1 for line in lines if line.strip().startswith("#"))
        comment_ratio = comment_lines / len(lines) if lines else 0

        tree = ast.parse(code)
        snake = 0
        camel = 0

        class NameVisitor(ast.NodeVisitor):
            def visit_FunctionDef(self, node):
                nonlocal snake, camel
                if "_" in node.name and node.name.islower():
                    snake += 1
                elif node.name[0].islower() and any(c.isupper() for c in node.name):
                    camel += 1

            def visit_Name(self, node):
                nonlocal snake, camel
                if isinstance(node.ctx, ast.Store):
                    if "_" in node.id and node.id.islower():
                        snake += 1
                    elif node.id[0].islower() and any(c.isupper() for c in node.id):
                        camel += 1

        NameVisitor().visit(tree)

        score = 30  # base
        if 0.1 <= comment_ratio <= 0.3:
            score += 40
        elif 0.05 <= comment_ratio < 0.1:
            score += 20
        elif comment_ratio > 0.3:
            score += 30
        if snake > camel:
            score += 30
        elif camel > 0:
            score += 15

        return {"comment_ratio": comment_ratio, "snake_case_count": snake, "camel_case_count": camel, "maintainability_score": min(score, 100)}

    def _analyze_duplication(self, code: str) -> dict:
        lines = code.split("\n")
        counts: dict[str, int] = {}
        for line in lines:
            s = line.strip()
            if s and not s.startswith("#"):
                counts[s] = counts.get(s, 0) + 1

        dups = [{"line": ln, "count": c} for ln, c in counts.items() if c > 1]
        ratio = len(dups) / len(lines) if lines else 0

        return {"duplicate_lines": len(dups), "duplicate_ratio": ratio, "duplicates": dups[:10]}
