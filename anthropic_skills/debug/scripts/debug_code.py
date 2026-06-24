#!/usr/bin/env python3
"""Python 代码调试工具 — 在隔离环境中执行代码，支持变量监视和异常捕获。"""

import json
import sys
import traceback


def _make_safe_builtins() -> dict:
    """构建安全的 __builtins__，替换危险函数。"""
    import builtins

    safe = dict(vars(builtins))
    # 替换危险函数
    safe["open"] = _safe_open
    safe["exec"] = _noop_dangerous
    safe["eval"] = _noop_dangerous
    safe["__import__"] = _noop_dangerous
    safe["compile"] = _noop_dangerous
    return safe


def _safe_open(*args, **kwargs):
    """受限的文件打开函数 — 仅允许读取。"""
    mode = args[1] if len(args) > 1 else kwargs.get("mode", "r")
    if "w" in mode or "a" in mode or "+" in mode or "x" in mode:
        raise PermissionError("写模式已禁用：调试环境仅允许读取文件")
    import builtins
    return builtins.open(*args, **kwargs)


def _noop_dangerous(*args, **kwargs):
    raise PermissionError(f"危险函数 {args[0] if args else ''} 已禁用")


def debug_code(code: str, variables: list[str] | None = None) -> dict:
    if variables is None:
        variables = []

    env: dict = {}
    safe_builtins = _make_safe_builtins()

    try:
        exec(code, {"__builtins__": safe_builtins}, env)
        return {
            "status": "success",
            "variables": {v: repr(env.get(v, "未定义")) for v in variables},
            "output": "代码执行成功",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_type": type(e).__name__,
            "error_message": str(e),
            "traceback": traceback.format_exc(),
            "variables": {v: repr(env.get(v, "未定义")) for v in variables},
        }


def main():
    import argparse

    parser = argparse.ArgumentParser(description="在隔离环境中调试 Python 代码")
    parser.add_argument("--code", required=True, help="需要调试/执行的 Python 代码")
    parser.add_argument("--variables", nargs="*", default=[], help="需要监视的变量名列表")

    args = parser.parse_args()

    if not args.code:
        print(json.dumps({"status": "error", "message": "code 不能为空"}, ensure_ascii=False))
        sys.exit(1)

    result = debug_code(args.code, args.variables)
    print(json.dumps(result, ensure_ascii=False))

    if result.get("status") == "error":
        sys.exit(1)


if __name__ == "__main__":
    main()
