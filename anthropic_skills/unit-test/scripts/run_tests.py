#!/usr/bin/env python3
"""单元测试执行工具 — 独立脚本，零外部依赖。"""

import importlib.util
import json
import sys
import unittest


def run_tests(test_file: str, test_class: str = "", test_method: str = "") -> dict:
    spec = importlib.util.spec_from_file_location("test_module", test_file)
    if spec is None or spec.loader is None:
        return {"status": "error", "message": f"无法加载测试文件: {test_file}"}

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    loader = unittest.TestLoader()
    if test_class and test_method:
        tests = loader.loadTestsFromName(f"{test_class}.{test_method}", module)
    elif test_class:
        test_class_obj = getattr(module, test_class, None)
        if test_class_obj is None:
            return {"status": "error", "message": f"测试类 {test_class} 不存在"}
        tests = loader.loadTestsFromTestCase(test_class_obj)
    else:
        tests = loader.loadTestsFromModule(module)

    runner = unittest.TextTestRunner(verbosity=2, stream=open(sys.devnull, "w"))
    result = runner.run(tests)

    total = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped)

    report = {
        "status": "ok",
        "tests_run": total,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "successful": total - failures - errors - skipped,
        "success_rate": round((total - failures - errors) / total * 100, 1) if total > 0 else 0,
    }

    if result.failures:
        report["failures_details"] = [
            {"test": str(t), "message": str(f[0]), "traceback": str(f[1])}
            for t, f in result.failures
        ]
    if result.errors:
        report["errors_details"] = [
            {"test": str(t), "message": str(e[0]), "traceback": str(e[1])}
            for t, e in result.errors
        ]

    return report


def main():
    import argparse

    parser = argparse.ArgumentParser(description="执行 Python 单元测试")
    parser.add_argument("--test-file", required=True, help="测试文件路径")
    parser.add_argument("--test-class", default="", help="特定测试类名（可选）")
    parser.add_argument("--test-method", default="", help="特定测试方法名（可选，需配合 --test-class）")

    args = parser.parse_args()

    if not args.test_file:
        print(json.dumps({"status": "error", "message": "test-file 不能为空"}, ensure_ascii=False))
        sys.exit(1)

    try:
        report = run_tests(args.test_file, args.test_class, args.test_method)
        print(json.dumps(report, ensure_ascii=False))
        if report.get("failures", 0) > 0 or report.get("errors", 0) > 0:
            sys.exit(1)
    except Exception as e:
        print(json.dumps({"status": "error", "message": f"测试执行失败: {e}"}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
