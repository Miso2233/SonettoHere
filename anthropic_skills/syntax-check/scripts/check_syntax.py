#!/usr/bin/env python3
"""语法检查工具 — 独立脚本，零外部依赖。"""

import ast
import json
import os
import subprocess
import sys
import tempfile


def check_python(code: str) -> dict:
    try:
        ast.parse(code)
        return {"language": "python", "errors": [], "warnings": []}
    except SyntaxError as e:
        return {
            "language": "python",
            "errors": [
                {
                    "line": e.lineno,
                    "column": e.offset,
                    "message": e.msg,
                    "type": "SyntaxError",
                }
            ],
            "warnings": [],
        }


def check_javascript(code: str) -> dict:
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".js", delete=False
        ) as f:
            f.write(code)
            tmp = f.name

        result = subprocess.run(
            ["node", "--check", tmp],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return {"language": "javascript", "errors": [], "warnings": []}
        else:
            return {
                "language": "javascript",
                "errors": [{"message": result.stderr.strip(), "type": "SyntaxError"}],
                "warnings": [],
            }
    except FileNotFoundError:
        return {"language": "javascript", "errors": [{"message": "Node.js 未安装", "type": "Error"}], "warnings": []}
    except Exception as e:
        return {"language": "javascript", "errors": [{"message": str(e), "type": "Error"}], "warnings": []}
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def check_typescript(code: str) -> dict:
    """TypeScript 检查：使用 tsc 或 ts-node。"""
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".ts", delete=False
        ) as f:
            f.write(code)
            tmp = f.name

        # 优先用 tsc --noEmit
        try:
            result = subprocess.run(
                ["npx", "--yes", "typescript", "--noEmit", "--lib", "esnext", tmp],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError:
            result = subprocess.run(
                ["node", "--check", tmp],
                capture_output=True,
                text=True,
                timeout=10,
            )

        if result.returncode == 0:
            return {"language": "typescript", "errors": [], "warnings": []}
        else:
            return {
                "language": "typescript",
                "errors": [{"message": result.stderr.strip() or result.stdout.strip(), "type": "SyntaxError"}],
                "warnings": [],
            }
    except FileNotFoundError:
        return {"language": "typescript", "errors": [{"message": "Node.js 未安装", "type": "Error"}], "warnings": []}
    except Exception as e:
        return {"language": "typescript", "errors": [{"message": str(e), "type": "Error"}], "warnings": []}
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="检查代码语法错误")
    parser.add_argument("--code", default="", help="需要检查的代码内容")
    parser.add_argument("--file", default="", help="代码文件路径（优先于 --code）")
    parser.add_argument(
        "--language", default="python", choices=["python", "javascript", "typescript"],
        help="语言类型",
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

    if args.language == "python":
        result = check_python(code)
    elif args.language == "javascript":
        result = check_javascript(code)
    elif args.language == "typescript":
        result = check_typescript(code)
    else:
        print(json.dumps({"status": "error", "message": f"不支持的语言: {args.language}"}, ensure_ascii=False))
        sys.exit(1)

    has_errors = len(result.get("errors", [])) > 0
    print(json.dumps({"status": "error" if has_errors else "ok", **result}, ensure_ascii=False))
    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()
