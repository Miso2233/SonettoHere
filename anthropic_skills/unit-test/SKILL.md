---
name: unit-test
description: 执行 Python 单元测试文件（unittest 框架），返回通过/失败/错误统计和详细报告。适用于用户想运行测试、验证代码正确性、排查测试失败原因时。
---

# Unit Test

执行 Python 单元测试文件（unittest 框架），支持按测试类、测试方法粒度运行，返回详细的测试报告。

## 脚本位置

`${SKILL_DIR}/scripts/run_tests.py`

运行方式：
```bash
uv run "${SKILL_DIR}/scripts/run_tests.py" --test-file PATH [--test-class CLASS] [--test-method METHOD]
```

## 使用方式

指定测试文件路径，可选指定测试类和方法：
- 运行整个测试文件：`--test-file tests/test_example.py`
- 运行特定测试类：`--test-file tests/test_example.py --test-class TestExample`
- 运行特定测试方法：`--test-file tests/test_example.py --test-class TestExample --test-method test_foo`

## 参数

| 参数 | 说明 |
|------|------|
| `--test-file PATH` | 测试文件路径（必填） |
| `--test-class CLASS` | 特定测试类名（可选） |
| `--test-method METHOD` | 特定测试方法名（可选，需配合 `--test-class`） |

## 执行流程

1. 使用 `importlib` 动态加载测试模块
2. 使用 `unittest.TestLoader` 按指定粒度加载测试用例
3. 使用 `unittest.TextTestRunner` 执行测试
4. 收集测试结果并生成报告

## 输出报告

```json
{
  "status": "ok",
  "tests_run": 10,
  "failures": 1,
  "errors": 0,
  "skipped": 1,
  "successful": 8,
  "success_rate": 90.0,
  "failures_details": [
    {
      "test": "test_foo (test_example.TestExample)",
      "message": "AssertionError: ...",
      "traceback": "Traceback (most recent call last):\n  ..."
    }
  ]
}
```

## 退出码

- `0` — 所有测试通过
- `1` — 存在失败或错误的测试

## 注意事项

- 仅支持 Python `unittest` 框架
- 测试文件路径必须在项目目录内
- 脚本零外部依赖，用 `uv run` 直接执行
