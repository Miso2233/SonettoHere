---
name: code-quality
description: 分析 Python 代码质量：复杂度（函数数/行数）、可维护性（注释率/命名规范）、重复代码检测。适用于用户想评估代码质量、重构前分析、Code Review 时。
---

# Code Quality

分析 Python 代码质量，包含三个维度：复杂度分析、可维护性评估、重复代码检测。用户可指定分析类型或进行全面分析。

## 脚本位置

`${SKILL_DIR}/scripts/analyze_quality.py`

运行方式：
```bash
uv run "${SKILL_DIR}/scripts/analyze_quality.py" [--code CODE] [--file PATH] [--analysis-type TYPE]
```

## 使用方式

在对话中提供需要分析的 Python 代码或文件路径。

## 参数

| 参数 | 说明 |
|------|------|
| `--code CODE` | 直接传入代码字符串 |
| `--file PATH` | 代码文件路径（优先于 `--code`） |
| `--analysis-type TYPE` | `complexity` / `maintainability` / `duplication` / `all`（默认） |

## 分析维度

### 1. 复杂度分析（complexity）
- 统计代码总行数
- 统计函数数量（含同步和异步函数）
- 计算函数平均长度
- 列出所有函数及其起止行号

### 2. 可维护性分析（maintainability）
- 注释率：注释行数 / 总行数
  - 10%~30%：+40 分（理想区间）
  - 5%~10%：+20 分
  - \> 30%：+30 分（可能过度注释）
- 命名规范：snake_case 和 camelCase 计数对比
  - snake_case 更多：+30 分
  - camelCase 存在但不多：+15 分
- 基础分 30，满分 100

### 3. 重复代码检测（duplication）
- 统计非空、非注释的重复行
- 计算重复比例
- 列出前 10 条重复行及出现次数

## 输出

```json
{
  "status": "ok",
  "complexity": {
    "total_lines": 120,
    "function_count": 5,
    "avg_function_length": 15.2,
    "functions": [{"name": "foo", "line": 1, "endline": 20}]
  },
  "maintainability": {
    "comment_ratio": 0.15,
    "snake_case_count": 8,
    "camel_case_count": 2,
    "maintainability_score": 85
  },
  "duplication": {
    "duplicate_lines": 3,
    "duplicate_ratio": 0.025,
    "duplicates": [{"line": "result = process(data)", "count": 3}]
  }
}
```

## 注意事项

- 依赖 Python 标准库 `ast`，零外部依赖
- 复杂度分析为静态行级度量，非 McCabe 圈复杂度
- 用 `uv run` 直接执行，无需安装
