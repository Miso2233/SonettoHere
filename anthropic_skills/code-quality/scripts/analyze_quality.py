#!/usr/bin/env python3
"""Python 代码质量分析工具 — 独立脚本，零外部依赖。"""

import ast
import json
import sys


def analyze_complexity(code: str) -> dict:
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

    return {
        "total_lines": total_lines,
        "function_count": len(functions),
        "avg_function_length": round(avg_len, 1),
        "functions": functions,
    }


def analyze_maintainability(code: str) -> dict:
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

    return {
        "comment_ratio": round(comment_ratio, 3),
        "snake_case_count": snake,
        "camel_case_count": camel,
        "maintainability_score": min(score, 100),
    }


def analyze_duplication(code: str) -> dict:
    lines = code.split("\n")
    counts: dict[str, int] = {}
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#"):
            counts[s] = counts.get(s, 0) + 1

    dups = [{"line": ln, "count": c} for ln, c in counts.items() if c > 1]
    ratio = len(dups) / len(lines) if lines else 0

    return {
        "duplicate_lines": len(dups),
        "duplicate_ratio": round(ratio, 3),
        "duplicates": dups[:10],
    }


def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="分析 Python 代码质量")
    parser.add_argument("--code", default="", help="需要分析的 Python 代码")
    parser.add_argument("--file", default="", help="代码文件路径（优先于 --code）")
    parser.add_argument(
        "--analysis-type", default="all",
        choices=["complexity", "maintainability", "duplication", "all"],
        help="分析类型",
    )

    args = parser.parse_args()

    code = args.code
    if args.file:
        try:
            code = read_file(args.file)
        except Exception as e:
            print(json.dumps({"status": "error", "message": f"文件读取失败: {e}"}, ensure_ascii=False))
            sys.exit(1)

    if not code:
        print(json.dumps({"status": "error", "message": "必须提供 code 或 file"}, ensure_ascii=False))
        sys.exit(1)

    try:
        result = {}
        at = args.analysis_type
        if at in ("complexity", "all"):
            result["complexity"] = analyze_complexity(code)
        if at in ("maintainability", "all"):
            result["maintainability"] = analyze_maintainability(code)
        if at in ("duplication", "all"):
            result["duplication"] = analyze_duplication(code)

        print(json.dumps({"status": "ok", **result}, ensure_ascii=False))
    except Exception as e:
        print(json.dumps({"status": "error", "message": f"质量分析失败: {e}"}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
