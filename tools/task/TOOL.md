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
