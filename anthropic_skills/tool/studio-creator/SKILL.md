---
name: studio-creator
description: 创建与编辑 SonettoHere 工作坊（studio）YAML 配置（studios/*.yaml）。当用户要求「新建/创建/编辑一个工作坊」、描述某个工作坊应包含的文件夹/工具/宏/技能/流程/规则，或需要生成工作坊配置时使用。工作坊配置会渲染为系统提示词注入 Agent，字段由 yamale schema 固定。
---

# 工作坊（Studio）创建

SonettoHere 的工作坊是 `studios/*.yaml` 文件：在会话顶栏选中后，后端按声明式 spec（`agent/studio.py` 的 `STUDIO_SPEC`）把该文件渲染为系统提示词的附加 Markdown 段落。本技能指导你**从零建立**或**编辑**工作坊，并用 yamale 校验字段、渲染脚本预览注入效果。

## 工作坊文件

- 目录：`studios/`（**git 忽略**，仅本地；可随时新增/编辑，即时生效，无需重启）
- **文件名 = 展示名**：文件名由 `name` 字段安全化生成，如 `本地 Obsidian 知识管理工作坊.yaml`
- `name` 全局唯一；渲染时按 `name`（回退文件名 stem）匹配
- 也可在侧栏「工作坊」管理页用表单可视化编辑，二者产出同一格式

## 字段结构

```yaml
name: 工作坊展示名（必填，唯一，同时作为文件名）
description: 简介（一句话概括）
role: 角色定位
main_folder:              # 主要文件夹（只允许写操作）
  - path: C:\绝对\路径
    note: 用途说明
additional_folders:       # 参考文件夹（可选读取）
  - path: C:\绝对\路径
    note: 用途说明
tools: [工具名]           # 推荐工具（如 file_read, tavily_search）
macros: [宏名]            # 推荐宏
skills: [技能名]          # 推荐技能
meta:                     # 元信息（键值对）
  version: 0.1.0
  created: 2026-08-01
body:
  structure: 目录结构多行文本（渲染为代码块）
  workflow: [步骤列表]
  rules: [规则列表]
  notes: [注意列表]
```

- 除 `name` 外所有字段**可省略**；缺失字段渲染为「（无）」
- 类型约定（由 `references/studio_schema.yaml` 固定）：
  - `main_folder` / `additional_folders`：元素为 `{path, note}` 字典
  - `tools` / `macros` / `skills` / `body.workflow` / `body.rules` / `body.notes`：字符串列表
  - `body.structure`：多行字符串；`meta`：任意键值对
- 路径用 Windows 绝对路径；反斜杠在 YAML plain scalar 中不转义，直接写 `C:\xxx`

## YAML 陷阱

- 普通标量内**不要**使用 ASCII 冒号+空格（`：` 后跟空格会被 YAML 当作映射分隔符导致解析失败）；用全角冒号 `：` 替代
- 列表项中的 `类型: 章节` 这类写法会报 `ScannerError`，务必改写为 `类型：章节`

## 工作流程

1. **确认需求**：问清工作坊定位（领域/角色）、主要文件夹（可写）、参考文件夹（可读）、推荐工具/宏/技能、工作流程、规则、注意事项。
2. **命名**：确定简洁中文 `name`；文件名随之。
3. **编写 YAML**：按上述结构写 `studios/<name>.yaml`（UTF-8）。
4. **校验**（yamale 固定字段）— 用 Python import 调用脚本函数：
   ```python
   import sys
   sys.path.insert(0, "${SKILL_DIR}/scripts")
   from validate_studio import validate_studio_file

   errors = validate_studio_file("studios/<name>.yaml")
   # errors 为空列表 = 通过；非空 = 字段错误列表，修复后重跑直到为空
   ```
5. **渲染预览**：
   ```python
   from render_studio import render_studio_file

   md = render_studio_file("studios/<name>.yaml")
   # md 即 Agent 注入的系统提示词段落，人工确认内容准确、无多余空段
   ```
   > 脚本是 Python 模块，直接 `import` 调用（Agent 用 py 脚本工具执行，无需 bash/uv run）。
6. **收尾**：汇报文件路径与渲染摘要；提醒用户在会话顶栏选择该工作坊以启用。

## 脚本与 schema

| 文件 | 作用（均为可 import 的 Python 模块） |
|---|---|
| `scripts/validate_studio.py` | `validate_studio_file(path) -> list[str]` — yamale 校验（字段由 schema 固定；管理页产生的 `null` 空列表自动规范化） |
| `scripts/render_studio.py` | `render_studio_file(path) -> str` — 渲染为注入用 Markdown（复用后端 `agent/studio.py`，保证一致） |
| `references/studio_schema.yaml` | yamale schema，固定字段、类型与嵌套结构 |

> **保持同步**：yamale schema 固定的是渲染器提取的字段。新增/调整字段时，必须同时更新 `references/studio_schema.yaml` 与 `agent/studio.py` 的 `STUDIO_SPEC`，否则校验与渲染不一致。
