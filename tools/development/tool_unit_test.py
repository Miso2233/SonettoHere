"""Tool: unit_test_runner — 单元测试执行。"""

import importlib.util
import unittest

from pydantic import BaseModel, Field

from tools.base import ToolBase, format_error, format_success


class UnitTestInput(BaseModel):
    get_doc: bool = Field(default=False, description="设为 true 以获取使用说明和领域知识")
    test_file: str = Field(default="", description="测试文件路径")
    test_class: str = Field(default="", description="特定测试类名（可选）")
    test_method: str = Field(default="", description="特定测试方法名（可选，需配合 test_class）")


class UnitTestTool(ToolBase):
    name: str = "unit_test_runner"
    description: str = (
        "执行 Python 单元测试文件，返回通过/失败/错误统计和详细报告。"
        "[调用积极性: 可自由看情况调用] [get_doc: 仅在发生错误时 get_doc]"
    )
    args_schema: type[BaseModel] = UnitTestInput

    def _run(
        self,
        get_doc: bool = False,
        test_file: str = "",
        test_class: str = "",
        test_method: str = "",
    ) -> str:
        if get_doc:
            return self._load_doc()
        if not test_file:
            return format_error("test_file 不能为空")

        try:
            spec = importlib.util.spec_from_file_location("test_module", test_file)
            if spec is None or spec.loader is None:
                return format_error(f"无法加载测试文件: {test_file}")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            loader = unittest.TestLoader()
            if test_class and test_method:
                tests = loader.loadTestsFromName(f"{test_class}.{test_method}", module)
            elif test_class:
                tests = loader.loadTestsFromTestCase(getattr(module, test_class))
            else:
                tests = loader.loadTestsFromModule(module)

            runner = unittest.TextTestRunner(verbosity=2)
            result = runner.run(tests)

            total = result.testsRun
            failures = len(result.failures)
            errors = len(result.errors)
            skipped = len(result.skipped)

            report = {
                "tests_run": total,
                "failures": failures,
                "errors": errors,
                "skipped": skipped,
                "successful": total - failures - errors - skipped,
                "success_rate": (total - failures - errors) / total * 100 if total > 0 else 0,
            }

            if result.failures:
                report["failures_details"] = [
                    {"test": str(t), "message": str(e[0]), "traceback": str(e[1])}
                    for t, e in result.failures
                ]
            if result.errors:
                report["errors_details"] = [
                    {"test": str(t), "message": str(e[0]), "traceback": str(e[1])}
                    for t, e in result.errors
                ]

            return format_success(report)
        except Exception as e:
            return format_error(f"测试执行失败: {e}")
