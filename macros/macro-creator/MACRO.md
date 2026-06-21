---
name: macro-creator
type: macro
version: 1.0
author: Sonetto
keywords: [创建宏, 新建宏, 写宏, macro, 工作流模板, 步骤指引]
description: 指导 Agent 创建新的 SonettoHere Macro。Macro 是轻量化的 Skill（Markdown 子集），不含脚本或外部依赖，一篇 MACRO.md 即可完成。适用场景：纯步骤指引、流程稳定频繁、无需外部依赖。当用户说"把这个流程写成宏"、"封装成宏"、"新建一个宏"、"写个宏"时使用。当用户要求创建一个仅包含流程指导的技能，也可以使用并评估创建宏是否更为合适。
category: 工具
---

# Macro Creator：创建新宏的工作流程

这是一个**关于宏的宏**（metamacro）。当用户想将某个稳定的工作流程封装成可复用的 Macro 时，按以下步骤操作。

---

## 第一步：理解 Macro 的核心定位

在开始之前，先确认当前任务**适合做 Macro**：

| 适合做 Macro | 不适合做 Macro |
|---|---|
| 纯步骤指引，不需要执行脚本 | 需要运行代码/调用 API |
| 流程稳定、会被频繁复用 | 一次性任务 |
| 无需外部依赖或领域知识库 | 需要大量参考文档支撑 |
| 逻辑简单，一篇 Markdown 能说清楚 | 内容超过 300 行 MACRO.md |

Macro 与 Skill 的核心区别：

- **Macro** — 只有 `MACRO.md`，无 `scripts/` `references/` `agents/` 等子目录
- **Skill** — 可包含 Python/JS 脚本、参考文档、评估工具等
- **Macro 的 YAML frontmatter** 中 `type: macro`（而非 skill 的默认 type）

---

## 第二步：确定 Macro 的基本信息

向用户确认以下内容（如果用户没有主动说全的话）：

1. **宏的名字**（name）— 简短、英文小写连字符，如 `exam-countdown`
2. **描述的触发场景**（description）— 什么时候该用这个宏，写清楚
3. **分类**（category）— 如「考试」「生活」「工具」「编程」等
4. **关键词**（keywords）— 帮助用户后续检索

---

## 第三步：创建目录和 MACRO.md

在 `macros/` 目录下创建子目录：

```
macros/<macro-name>/
└── MACRO.md
```

MACRO.md 的 YAML frontmatter 格式：

```yaml
---
name: <宏的英文标识>
type: macro          # 固定值，区分 macro 与 skill
version: 1.0         # 语义化版本
author: Sonetto      # 或用户的名字
keywords: [关键词1, 关键词2]
description: >-
  用一句话描述什么时候该用这个宏。
  这是 Agent 匹配宏的主要依据，写清楚触发场景。
category: <分类名>
---
```

### frontmatter 字段说明

| 字段 | 必填 | 说明 |
|---|---|---|
| `name` | 是 | 宏的英文标识，用连字符连接，如 `exam-countdown` |
| `type` | 是 | 固定为 `macro`，用于 SonettoHere 区分 Macro 和 Skill |
| `version` | 推荐 | 语义化版本号，如 `1.0`、`1.1` |
| `author` | 可选 | 创建者名字 |
| `keywords` | 推荐 | 搜索关键词列表 |
| `description` | 推荐 | 触发描述，告诉 Agent 什么场景该用此宏 |
| `category` | 可选 | 分类名，如「考试」「生活」「工具」 |

---

## 第四步：编写 MACRO.md 正文

正文按以下结构组织：

### 标题

直接用宏的名字作为一级标题，或者用中文描述性标题。

### 适用场景

用简短的段落说明这个宏在什么情况下使用。可以用举例的方式。

### 工作流程

用二级标题有序列表（1. 2. 3.）列出每一步操作。每个步骤说明：
- **做什么** — 具体的操作描述
- **为什么** — 做这一步的原因（可选，帮助理解）
- **注意什么** — 边界情况或常见陷阱（可选）

### 输入输出（如有）

如果宏需要用户提供信息或会产出文件，在这里说明。

### 示例（推荐）

给出 1~2 个具体的使用示例，方便理解。

### 相关宏和技能（可选）

列出与其他宏和技能的关联。

---

## 第五步：与用户确认

写完后，向用户展示宏的内容，确认：
- 名字和描述是否准确
- 步骤是否完整
- 是否有遗漏的边界情况

根据反馈修改，直到用户满意。

---

## 示例：一个完整的 MACRO.md 骨架

```markdown
---
name: example-macro
type: macro
version: 1.0
author: Sonetto
keywords: [示例, 模板, 参考]
description: 这是一个示例宏的模板。当你需要参考 Macro 的格式来创建新宏时使用。
category: 工具
---

# 示例宏

这是一个示例，展示了 Macro 的标准格式。

## 适用场景

当你需要...

## 工作流程

1. **第一步**：做某事
   - 具体操作说明
2. **第二步**：做另一件事
   - 具体操作说明

## 输入

- 用户需要提供...

## 输出

- 生成的文件路径...
```

---

## 注意事项

1. **保持简短** — Macro 的优势就是轻量，MACRO.md 尽量控制在 200 行以内。如果超过 200 行，考虑其中部分内容是否适合拆成另一个宏，或者是否应该升级为 Skill。
2. **不要放脚本** — Macro 不包含 `scripts/` 目录。如果流程需要运行代码，说明它应该是一个 Skill 而非 Macro。
3. **不要放参考文档** — Macro 不包含 `references/` 目录。如果需要大量领域知识，升级为 Skill。
4. **description 是给 Agent 看的** — 写清楚触发条件，但不要过度冗长。Agent 会根据这段描述决定是否调用这个宏。
5. **步骤要可执行** — 每一步都应该是 Agent 能直接执行的具体操作，而不是抽象概念。
