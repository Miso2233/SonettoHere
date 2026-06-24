---
name: debug
description: 在隔离沙箱中执行 Python 代码，支持变量监视、异常捕获和堆栈跟踪。适用于用户想调试代码片段、验证逻辑、排查运行时错误时。
---

# Debug

在隔离的 Python 沙箱环境中执行代码片段，支持变量监视和异常捕获，用于快速调试和验证代码逻辑。

## 脚本位置

`${SKILL_DIR}/scripts/debug_code.py`

运行方式：
```bash
uv run "${SKILL_DIR}/scripts/debug_code.py" --code CODE [--variables VAR1 VAR2 ...]
```

## 使用方式

在对话中提供需要调试的 Python 代码和需要监视的变量名列表。

## 参数

| 参数 | 说明 |
|------|------|
| `--code CODE` | 需要调试/执行的 Python 代码（必填） |
| `--variables [VAR ...]` | 需要监视的变量名列表（可选，空格分隔） |

## 功能

### 1. 隔离执行
- 使用 `exec()` 在安全的沙箱环境中执行代码
- 替换危险函数：`open`（只读模式）、`exec`、`eval`、`__import__`、`compile` 均被禁用

### 2. 变量监视
- 指定需要监视的变量名列表
- 执行后返回各变量的 `repr()` 值
- 如果变量未定义，显示 `"未定义"`

### 3. 异常捕获
- 捕获执行过程中的所有异常
- 返回异常类型、异常消息、完整堆栈跟踪
- 即使异常发生，已赋值的变量仍然可查

## 输出

执行成功：
```json
{
  "status": "success",
  "variables": {"result": "[1, 2, 3, 4, 5]"},
  "output": "代码执行成功"
}
```

执行失败：
```json
{
  "status": "error",
  "error_type": "ZeroDivisionError",
  "error_message": "division by zero",
  "traceback": "Traceback (most recent call last):\n  ...",
  "variables": {"x": "10", "y": "0"}
}
```

## 退出码

- `0` — 代码执行成功
- `1` — 执行时发生异常

## 注意事项

- 代码在隔离沙箱中执行，不污染外部状态
- 写文件操作被禁止（仅允许读模式打开文件）
- 所有危险函数（exec、eval、import 等）被禁用
- 适合快速验证小段代码逻辑
- 脚本零外部依赖，用 `uv run` 直接执行
