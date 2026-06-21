# Todoist 任务管理 API 参考

## 工具列表

| 工具 | 功能 | 备注 |
|------|------|------|
| `todo_list_projects` | 列出所有项目及板块信息 | 添加/移动任务前先调用，确认项目名存在 |
| `todo_list_sections` | 列出指定项目下的所有板块 | 可按 project_name 筛选 |
| `todo_list_labels` | 列出所有标签 | 当前无已定义标签 |
| `todo_list` | 列出未完成任务，支持筛选 | 参数：project_name / section_name / label / parent_id / ids / limit |
| `todo_query` | 按 task_id 查询单个任务详情 | 查不到时回退到 todo_list |
| `todo_add` | 添加新任务 | 完整参数控制 |
| `todo_add_quick` | 快速添加任务 | 单字符串语法：内容 #项目 @标签 p3 明天下午 |
| `todo_update` | 更新任务属性 | 支持 content / due / priority / description / labels / project_name / section_name 等 |
| `todo_complete` | 完成任务 | 按 task_id |
| `todo_uncomplete` | 重新打开已完成任务 | 按 task_id |
| `todo_delete` | 删除任务 | 按 task_id |

## 操作规范

### 添加任务（todo_add）

**前置条件**：
1. 用户表达相对时间（"明天""下周"）时，先通过 time_tool 获取当前日期再换算
2. 调用 `todo_list_projects` 确认 project_name 存在

**参数说明**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `content` | string | 任务名称，必填 |
| `description` | string | 任务备注/描述 |
| `due_string` | string | 自然语言截止时间（优先使用），与 due_date / due_datetime 互斥 |
| `due_date` | string | 精确日期 `YYYY-MM-DD` 或 `YYYY-MM-DD HH:MM` |
| `project_name` | string | 项目名，大小写敏感，需先确认存在 |
| `section_name` | string | 板块名，需先确认该板块存在于目标项目中 |
| `priority` | int | 1=低 / 2=中 / 3=高 / 4=紧急。仅用户明确表达紧急意图时用 p4 |
| `labels` | string[] | 标签名列表 |
| `auto_reminder` | bool | 设置了时间时自动添加默认提醒 |
| `duration` | int | 预估时长数值（配合 duration_unit） |
| `duration_unit` | "minute" \| "day" | 时长单位 |
| `deadline_date` | string | ⚠️ 硬截止日期，当前 Todoist API 可能不支持（曾返回 403） |

### 快速添加（todo_add_quick）

单字符串语法，一行搞定。Todoist 自动解析其中的 `#项目名` `@标签` 和自然语言时间。

```
content: "买牛奶 #购物  明天下午3点 p2"
```

可选参数：
- `note` — 附加备注
- `reminder` — 提醒时间自然语言描述
- `auto_reminder` — 默认 true

### 更新任务（todo_update）

支持修改 content、description、due_string/date/datetime、priority、labels、assignee_id、order、duration、deadline_date、project_name、section_name 等字段。

**⚠️ 不稳定用法提醒**：
- **板块间移动**：将任务从无板块状态移入板块（`section_name`），或跨板块移动时，当前实现可能返回 400 错误。稳定替代方案：删除原任务后在目标板块重新创建。
- **deadline_date**：Todoist API 可能返回 403，不确定是否已开放。如遇错误，建议改用手动备注。

### 查询任务

- `todo_list` — 批量查询，支持按 project_name / section_name / label 筛选
- `todo_query` — 单条精确查询，按 task_id。查不到时回退到 todo_list

## 错误处理对照表

| 错误场景 | 推荐处理方式 |
|----------|------------|
| content 为空 | 提示用户提供任务名称 |
| project_name 不存在 | 列出可用项目供用户确认 |
| task_id 无效 | 列出全部任务让用户确认 |
| due_date 格式错误 | 换一种格式重试，仍失败则请求用户提供准确时间 |
| 板块移动报 400 | 删除 + 重建，在目标板块重新添加 |
| deadline_date 报 403 | 改用 description 备注硬截止日期 |
