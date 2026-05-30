# Kaleidoscope Project — 阶段进度报告

> 更新日期：2026-05-17

## 一、总体进度

| 阶段 | 状态 |
|------|------|
| Phase 1 — 基础设施 | ✅ 完成 |
| Phase 2 — 首批工具气泡 | ✅ 完成 |
| Phase 3 — 逐工具迁移 | ✅ 完成（20/21 工具，1 个因架构原因暂缓） |

## 二、已开发气泡清单

| # | 气泡组件 | 覆盖后端 tools | 行数 | 复杂度 |
|---|---------|---------------|------|--------|
| 1 | BilibiliDownloadBubble | `bilibili_download` | ~180 | 中（封面+按钮） |
| 2 | TodoBubble | `todo_add/list/complete/uncomplete/delete/update/query/list_projects` (8) | ~350 | 中（三种视图） |
| 3 | TaskTrackerBubble | `task_tracker` | ~120 | 低（进度条） |
| 4 | PythonBubble | `run_python` | ~180 | 中（语法高亮） |
| 5 | FilesBubble | `file_operations`, `file_read`, `file_write`, `file_list` | ~250 | 中（读写列三种状态） |
| 6 | TarotBubble | `tarot` | ~200 | 中（卡片+翻牌动画） |
| 7 | AnswerBookBubble | `answer_book` | ~100 | 低（问答卡片） |
| 8 | MapBubble | `nearby_search`, `fuzzy_address_search`, `geocode_address`, `get_transit_route`, `get_cycling_route` (5) | ~350 | 高（POI/路线/骑行） |
| 9 | WeatherBubble | `get_current_weather` | ~180 | 中（渐变背景+预报） |
| 10 | HolidayBubble | `holiday_calendar` | ~240 | 中（日/月/年三种模式） |
| 11 | TimeBubble | `time_skill` | ~140 | 低（大字时钟） |
| 12 | SyntaxBubble | `syntax_checker` | ~170 | 低（错误列表） |
| 13 | CookieBubble | `bilibili_set_cookie` | ~100 | 低（状态信息） |
| 14 | ImageBubble | `analyze_image` | ~120 | 低（markdown 渲染） |
| 15 | SearchBubble | `smart_search` | ~475 | 中（结果列表+调试面板） |
| 16 | PdfReaderBubble | `pdf_reader` | ~300 | 中（元数据/目录/文本/搜索） |
| 17 | DocReaderBubble | `doc_reader` | ~300 | 中（元数据/段落/表格/搜索） |
| 18 | CodeQualityBubble | `code_quality_analyzer` | ~250 | 中（复杂度/可维护性/重复度） |
| 19 | UnitTestBubble | `unit_test_runner` | ~300 | 中（通过率/失败详情） |
| 20 | ScraperBubble | `scrape_webpage` | ~260 | 中（页面信息/链接/图片/结构化数据） |

**统计：** 20 个气泡组件覆盖 31 个后端 tool_name。

## 三、技术架构回顾

### 3.1 数据流

```
Skill (format_success JSON)
  → LangChain ToolMessage (.content)
    → websocket_callback._extract_tool_data()
      → WebSocket tool_end.tool_data
        → useChat.ts handleEvent('tool_end')
          → ToolBubbleRouter → registry → XxxBubble.vue
```

### 3.2 关键发现

- **LangChain ToolMessage 陷阱**：`on_tool_end` 的 `output` 是 ToolMessage 对象，必须走 `._extract_content()` 取 `.content` 属性，不能直接 `str()`。
- **Playground 先行的价值**：用 mock 数据隔离前端组件问题与后端数据管道问题，快速定位根因。
- **UAPI 字段名映射**：后端 API 返回的字段名通常为 snake_case（如 `temp_max`），需在 extractor 中映射为前端使用的格式。

### 3.3 工具气泡标准接口

```typescript
// Props
defineProps<{ toolCall: ToolCall }>()
// Emits
defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()
// 数据源（统一 fallback 策略）
const td = computed(() => toolCall.toolData ?? JSON.parse(toolCall.output).data ?? {})
// 三种状态
toolCall.status === 'running' | 'done' | 'error'
```

## 四、项目总结

Kaleidoscope 项目已结束。**20/21 个工具已覆盖**，仅 `ask_user_for_info` 因需要前端工具系统重构（特殊交互模式）而暂缓，待后续单独处理。

详细总结参阅 [kaleidoscope-completion-report.md](./kaleidoscope-completion-report.md)。

## 五、经验与教训

### 5.1 踩坑记录

1. **ToolMessage.content**：所有 `_extract_tool_data` 分支必须用 `_extract_content(output)`。
2. **1622 错误（字段不匹配）**：天气提取器假设 `temp`/`condition`/`wind`，UAPI 实际返回 `temperature`/`weather`/`wind_direction` + `wind_power`。修复方法：参考官方 API 文档重新映射。
3. **节假日数据结构重构**：从扁平结构改为 `mode/days[]/holidays[]/nearby{}`，导致前后端同步重写。

4. **BubbleChrome 溢出裁切**：折叠动画后 `maxHeight` 固定不变，内部展开会溢出。修复方案：动画完成后将 `maxHeight` 设为 `none`。

### 5.2 开发建议

- 新工具气泡优先选择简单类型（如 `time_skill` 约 140 行），熟悉流程后再做复杂组件。
- `toolData` 缺失时应优雅降级到 `raw-output` 文本显示，不可白屏。
- 每个气泡的 `td` computed 使用统一的 fallback 策略：`toolData → output.data → {}`。
