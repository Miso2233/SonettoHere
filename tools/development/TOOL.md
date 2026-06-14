# 开发工具领域知识

## 可用 Skill
| Skill | 功能 | 语言支持 |
|-------|------|---------|
| `syntax_checker` | 语法检查 | Python (ast), JavaScript/TypeScript (node --check) |
| `code_quality_analyzer` | 质量分析 | Python（复杂度/可维护性/重复检测） |
| `unit_test_runner` | 单元测试执行 | Python (unittest) |
| `debugger` | 代码调试 | Python（exec + 变量检查 + 堆栈跟踪） |

## 技能协作流程
- **语法检查 → 质量分析**：先确认代码无语法错误，再做质量分析
- **质量分析 → 测试**：分析报告指出问题区域后，针对性编写/运行测试
- **调试 → 修复**：debugger 捕获异常后，修复代码再重新检查

## 常见陷阱
- **syntax_checker** 的 JS/TS 检查依赖 Node.js 环境，若未安装会报错
- **code_quality_analyzer** 仅支持 Python 代码（使用 ast 模块解析）
- **unit_test_runner** 动态加载测试文件，测试文件中的顶层代码也会执行
- **debugger** 的 breakpoints 参数目前仅做记录，不实际设置断点；主要用于变量检查和异常捕获
