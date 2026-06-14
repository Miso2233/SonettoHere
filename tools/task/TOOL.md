# 任务追踪领域知识

## task_tracker
无状态任务清单追踪工具。用于管理和跟踪待办任务列表。

## 使用方式
每次调用传入完整的 todos 列表，工具会统计各状态数量并返回摘要。
工具不维护内部状态，LLM 需要在每次调用时提供完整的最新进展。

## 参数格式
```json
{
  "todos": [
    {"content": "分析需求",         "status": "completed",   "activeForm": "分析需求"},
    {"content": "实现功能模块",     "status": "in_progress", "activeForm": "编写代码"},
    {"content": "编写单元测试",     "status": "pending",     "activeForm": "编写测试用例"},
    {"content": "更新文档",         "status": "pending",     "activeForm": "更新文档"}
  ]
}
```

## 状态说明
- `pending` — 待开始
- `in_progress` — 进行中（同时只能有一个）
- `completed` — 已完成

## 字段说明
- `content` — 任务描述
- `status` — 任务状态
- `activeForm` — 进行中状态的动名词描述，用于前端显示"正在……"标签

## 任务状态语义（前端自动显示的标签）

前端顶栏会根据任务清单的组合自动渲染一个状态词，LLM 应通过调整任务列表来传达当前阶段意图：

| 任务清单特征 | 显示标签 | 含义 |
|---|---|---|
| 仅 `pending` | 就绪 | 用户已确认目标，等待指示开始 |
| 混合 `pending` + `completed` | 待命 | 用户中断了当前任务，等待进一步指示 |
| 仅 `completed` | 已完成 | 全部完成 |
| `in_progress` + `pending`，无 `completed` | 出发 | LLM 正在按计划推进，尚未完成任何子任务 |
| `in_progress` + `pending` + `completed` | 工作中 | LLM 正在推进，已有子任务完成 |

### 使用准则

1. **默认启动方式**：用户首次提出任务时，LLM 应立即拆解子任务，将第一个子任务设为 `in_progress`，其余 `pending`。此时顶栏显示"出发"——标记 LLM 已开始自主推进。
2. **就绪态**：如果用户说"准备好了叫我"、"先准备好等我指令"等，LLM 应将所有任务设为 `pending`（无 `in_progress`）。此时顶栏显示"就绪"——标记 LLM 已准备完毕，等待用户发令。
3. **待命态**：如果用户说"先停一下"、"待命"、"等我确认"等，LLM 应移除所有 `in_progress`，保持已有 `completed` 不变，其余设为 `pending`。此时顶栏显示"待命"——标记任务被用户中断。
4. **恢复推进**：用户说"继续"时，LLM 恢复一个 `in_progress`，顶栏回到"工作中"或"出发"。
5. **同时只有一个 in_progress**：任何时候最多一个任务为 `in_progress`，推进到下一项时把上一项改为 `completed`。
