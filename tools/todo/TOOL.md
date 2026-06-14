# Todoist 任务管理领域知识

## 技能协作流程
- 添加任务前，先调用 `todo_list_projects` 确认项目名是否存在
- 如果用户说"明天下午"、"下周"等相对时间，先调用 `time_skill` 获取当前日期再转换
- 任务完成后，建议调用 `todo_list` 确认状态已更新
- `todo_query` 查不到任务时，先用 `todo_list` 列出全部任务再筛选

## 常见陷阱
- 优先级 4（紧急）仅在用户明确表达"非常急/立刻/马上"时使用
- 不要在未确认项目存在时直接填写 project_name
- 多个任务需分别调用 `todo_add`，不要试图合并为一次调用

## 参数约定
- `due_date` 支持自然语言（明天下午3点、下周五）或 `YYYY-MM-DD HH:MM`
- `project_name` 大小写敏感，必须与 Todoist 中实际项目名一致
- `priority`：1=低, 2=中, 3=高, 4=紧急

## 错误处理规范
| 错误场景 | 处理方式 |
|----------|----------|
| content 为空 | 提示用户提供任务名称 |
| project_name 不存在 | 调用 `todo_list_projects` 列出可用项目供用户选择 |
| task_id 无效 | 调用 `todo_list` 列出任务后让用户确认 |
| due_date 格式错误 | 尝试重新解析，或让用户提供明确格式 |
