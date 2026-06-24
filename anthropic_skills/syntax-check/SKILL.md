---
name: syntax-check
description: 检查代码语法错误，支持 Python（ast.parse）、JavaScript（node --check）、TypeScript（tsc）。适用于用户想检查代码语法、排查编译错误、验证代码片段正确性时。
---

# Syntax Check

检查代码语法错误。支持 Python、JavaScript、TypeScript 三种语言的语法检测，可接受直接传入代码字符串或指定文件路径。

## 脚本位置

`${SKILL_DIR}/scripts/check_syntax.py`

运行方式：
```bash
uv run "${SKILL_DIR}/scripts/check_syntax.py" [--code CODE] [--file PATH] [--language LANG]
```

## 使用方式

在对话中提供需要检查的代码或文件路径，Claude 会调用脚本执行检查。

## 支持的语言

| 语言 | 检测方式 | 前提条件 |
|------|----------|----------|
| Python | `ast.parse()` | 无（标准库） |
| JavaScript | `node --check` | Node.js |
| TypeScript | `npx typescript --noEmit` | Node.js |

## 参数

| 参数 | 说明 |
|------|------|
| `--code CODE` | 直接传入代码字符串 |
| `--file PATH` | 代码文件路径（优先于 `--code`） |
| `--language LANG` | 语言：`python` / `javascript` / `typescript`（默认 `python`） |

## 输出

检查通过：
```json
{"status": "ok", "language": "python", "errors": [], "warnings": []}
```

检查失败（含具体行号、列号、错误消息）：
```json
{"status": "error", "language": "python", "errors": [{"line": 5, "column": 8, "message": "invalid syntax", "type": "SyntaxError"}], "warnings": []}
```

## 注意事项

- Python 检查使用标准库 `ast`，无需额外依赖
- JS/TS 检查依赖本地 Node.js 运行时
- 仅做语法层面的静态检查，不执行代码
- 脚本零外部依赖，可用 `uv run` 直接执行
