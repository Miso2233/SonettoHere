# 组件层 — `components/`

## 层级定位

**UI 展示与交互层**，负责渲染数据、响应用户操作。组件是纯展示/交互单元，不直接管理业务状态（通过 composables 或 props 获取数据）。

## 组件分类

### 页面级容器组件（在 views/ 中使用）

| 组件 | 用途 |
|---|---|
| `ChatWindow.vue` | 聊天消息列表容器 — 合并已完成轮次和流式轮次，自动滚动 |
| `ChatInput.vue` | 聊天输入框 — 文本输入、引用管理、发送/停止、拖拽缩放 |
| `SessionSidebar.vue` | 侧栏会话列表 — 会话切换、删除、固定、标题生成 |

### 展示/功能组件

| 组件 | 用途 |
|---|---|
| `MessageBubble.vue` | 消息气泡 — 用户/助手消息 + 引用 chip + 图片缩略图 |
| `ThinkingBlock.vue` | 思考块 — LLM 思考过程展示，流式 spinner + Markdown 渲染 |
| `RenderMarkdown.vue` | Markdown 渲染 — markdown-it → HTML，流式时禁用 iframe 沙箱 |
| `HtmlSandbox.vue` | iframe 沙箱沙箱 — 隔离 LLM 输出的原始 HTML/JS/CSS |
| `ToolCallCard.vue` | 工具调用卡片 — 显示工具名、输入、输出、耗时 |
| `ToolBubbleRouter.vue` | 工具气泡路由 — 根据工具类型分发到不同展示组件 |
| `ContextUsageBadge.vue` | 上下文用量徽章 — Token 占用百分比 + 模型名 |
| `TaskTrackerBar.vue` | 任务追踪栏 — task_tracker 工具进度展示 |
| `StatusBadge.vue` | 连接状态指示器 — WS 连接 + 后端健康状态 |
| `ReferenceChip.vue` | 引用 chip — 文件/链接引用小标签 |
| `ImageThumbnail.vue` | 图片缩略图 — 本地图片预览 |
| `HealthPanel.vue` | 健康面板 — 后端各组件健康状态列表 |
| `ContextMenu.vue` | 右键上下文菜单 — 引用/复制/撤回 |
| `MarkdownEditor.vue` | CodeMirror Markdown 编辑器 |
| `AutocompletePanel.vue` | 自动补全面板 — @技能 / #工具 / !宏补全 |
| `Icon.vue` | SVG 图标组件 |
| `MemoryPanel.vue` | 记忆面板 — 后台记忆更新日志 |
| `MomentCard.vue` | 时刻卡片 — 「此刻」功能 |
| `NewsCard.vue` | 新闻卡片 — 系统更新动态 |
| `SectionCard.vue` | 分区卡片 — 记忆瀑布流分区 |

## 核心组件详解

### ChatWindow.vue — 聊天消息列表

**数据流**：

```
props: turns, currentTurn, error
  ↓
mergedTurns = computed(() => {
  if currentTurn 且不在 turns 中 → [...turns, currentTurn]
  else → turns
})
  ↓
v-for="turn in mergedTurns"  (key: turn.id — 确保过渡时不销毁重建)
  ├── MessageBubble (用户消息)
  ├── v-for="ev in turn.events"
  │   ├── ev.kind === 'thinking' → ThinkingBlock
  │   └── ev.kind === 'tool' → ToolBubbleRouter
  ├── v-if="turn.finalAnswer" → MessageBubble (助手消息，已完成的轮次)
  └── v-if="turn.memoryEvents?.length" → 记忆更新日志
```

**自动滚动机制**：

```typescript
// 三个 watch 分别覆盖不同场景
watch(() => props.turns.length,           // 新轮次完成
  () => { if (isNearBottom()) scrollToBottom() })
watch(() => props.currentTurn?.events.length,  // 新事件（新 token/新工具调用）
  () => { if (isNearBottom()) scrollToBottom() })
watch(() => props.currentTurn?.finalAnswer,    // 最终答案到达
  () => { if (isNearBottom()) scrollToBottom() })
```

**becameAnswer 处理**：

`hasAnswerBlock(turn)` 检测 turn.events 中是否存在 `becameAnswer = true` 的 ThinkingBlock。若存在，`finalAnswer` 的 `MessageBubble` 被隐藏（"思考已转化为答案"），避免同一内容重复显示。

### ThinkingBlock.vue — 流式思考过程

```
┌──────────────────────────────────────┐
│ 思考中……  ◌                          │  ← 未完成时显示 spinner
│ ─────────────────────────────────── │
│ <RenderMarkdown :content="block.tokens"
│                   :streaming="!block.done" />
└──────────────────────────────────────┘
         ↓ (done = true)
┌──────────────────────────────────────┐
│ 思考中（完成）                        │  ← 标题区域折叠（max-height:0）
│ ─────────────────────────────────── │
│ <RenderMarkdown :content="block.tokens"
│                   :streaming="false" />
└──────────────────────────────────────┘
```

关键行为：
- **CSS 折叠标题**：`done` 时 `.thinking-header` 的 `max-height` 过渡为 0，`opacity` 过渡为 0
- **样式切换**：`done` 时背景从 `bg-secondary` 变为 `bg-card`，边框转为气泡样式
- **spinner 自动消失**：`v-if="!block.done"` 控制 spinner 出现/消失

### RenderMarkdown.vue + HtmlSandbox.vue — 安全渲染

**双模式渲染策略**：

```
RenderMarkdown
  ├── streaming=true → 直接 v-html（无沙箱，避免 iframe 频繁重建）
  │                     contentNeedsIsolation() 不执行
  └── streaming=false → contentNeedsIsolation(content) 检测
       ├── 含脚本/样式 → HtmlSandbox (sandboxed iframe)
       └── 不含       → 直接 v-html
```

**HtmlSandbox iframe 沙箱**：

iframe 使用 `sandbox="allow-scripts allow-modals"` 属性：
- 禁止导航、禁止弹窗、禁止表单提交、禁止同源访问
- 只允许脚本执行和模态对话框

内部通过 `parent.postMessage()` 上报：
- `sandbox-resize` — 内容高度变化 → 父窗口调整 iframe 高度
- `sandbox-error` — JS 运行时错误 → 父窗口错误面板显示

**dangerous content 检测** (`contentNeedsIsolation()` in `utils/markdown.ts`)：

```
检测项：
  <script> / </script>           ← JS 脚本
  <style> / </style>             ← 全局 CSS（泄漏到气泡外）
  <link rel="stylesheet">        ← 外部 CSS
  onXxx="..."                    ← 内联事件处理器
  href="javascript:..."          ← 伪协议 URL
  <iframe>                       ← 嵌套框架

但会跳过 ``` 非 html 代码块内的内容
```

### ChatInput.vue — 智能输入框

**功能集成度最高的组件**（~44KB，含完整模板）：

| 功能 | 说明 |
|---|---|
| 文本输入 | `textarea` + 自动高度 + `Enter` 发送 / `Shift+Enter` 换行 |
| 引用管理 | 文件/链接引用 chip，`@` 触发补全，blocked 状态标记 |
| 拖拽缩放 | `pointerdown` → `pointermove` 调整输入框高度（localStorage 持久化） |
| 模式切换 | 私密模式 / 自动执行 / 图像认知模式 |
| 模型选择 | 提供商下拉 + 模型下拉（从 `api.listProviders()` 获取） |
| 发送/停止 | 流式时显示停止按钮，空闲时显示发送按钮 |
| 图片预览 | 拖拽/粘贴图片 → 缩略图预览 → 上传 |
| 自动补全 | `@技能` / `#工具` / `!宏` 补全面板 |
| 链接输入 | 点击链接按钮 → URL 输入栏 → 生成引用 chip |

## 设计要点

### 1. turn.id 作为 key 防止组件销毁重建

```html
<template v-for="(turn, mergedIdx) in mergedTurns" :key="turn.id">
```

当 turn 从 `currentTurn` 过渡到 `turns`（即 `done` 事件触发后），由于使用 `turn.id` 作为 key，Vue 复用同一组件实例而非销毁重建。这对包含 iframe 的 `HtmlSandbox` 尤其重要——避免 iframe 闪动和重载。

### 2. 助手侧 hover 显示记忆日志

```css
.assistant-side .memory-tool-log {
  opacity: 0;
  transition: opacity 0.15s ease;
}
.assistant-side:hover .memory-tool-log {
  opacity: 1;
}
```

记忆更新日志默认透明隐藏，用户 hover 助手区域时淡入显示。这是为了在轮次较多时保持界面清爽。

### 3. 流式渲染的沙箱降级策略

| 渲染阶段 | 沙箱状态 | 原因 |
|---|---|---|
| 流式接收中 | 禁用 | 避免 token 到达 → iframe 重建 → 闪动 |
| 流式完成 | 按需启用 | 检测到危险内容时启用，否则继续 v-html |
