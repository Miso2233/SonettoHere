# 前端架构评审与维护指南

> 编写日期：2026-07-13
> 目标读者：SonettoHere 前端贡献者

## 目录

1. [架构概览](#1-架构概览)
2. [隐式共享状态模式（核心架构决策）](#2-隐式共享状态模式核心架构决策)
3. [可引入但未使用的设计模式](#3-可引入但未使用的设计模式)
4. [难以维护的点](#4-难以维护的点)
5. [改进建议](#5-改进建议)
6. [附录：文件职责速查](#6-附录文件职责速查)

---

## 1. 架构概览

```
web/
├── src/
│   ├── main.ts              # 入口：挂载 App + Router
│   ├── App.vue              # 根组件：侧栏布局 + 路由出口
│   ├── env.d.ts             # 全局类型声明
│   │
│   ├── router/index.ts      # Vue Router 路由定义（9 个路由，4 个懒加载）
│   │
│   ├── api/index.ts         # API 层：封装 fetch，统一认证 Token
│   │
│   ├── types/index.ts       # 全局 TypeScript 类型定义（500 行）
│   │
│   ├── composables/         # 组合式函数（状态层）
│   │   ├── useChat.ts       # WebSocket 连接 + 消息状态 + localStorage 持久化
│   │   ├── useSession.ts    # 会话生命周期管理（CRUD + 切换）
│   │   ├── useHealth.ts     # 后端健康检查轮询
│   │   └── useSidebar.ts    # 侧栏折叠状态（含窄屏自适应）
│   │
│   ├── views/               # 页面组件
│   │   ├── ChatView.vue         # 主聊天界面
│   │   ├── MemoryView.vue       # 记忆界面（委托给 MemoryPanel）
│   │   ├── NewsView.vue         # 更新动态 + 版本时间轴
│   │   ├── ProvidersView.vue    # LLM 提供商管理（CRUD 表单）
│   │   ├── SoulView.vue         # 人设编辑（委托给 MarkdownEditor）
│   │   ├── UserView.vue         # 用户设定编辑（委托给 MarkdownEditor）
│   │   ├── PathWhitelistView.vue # 路径白名单管理
│   │   ├── SonettoBlockerView.vue # 拒止锚管理
│   │   ├── EnvVarsView.vue       # 环境变量管理
│   │   └── PlaygroundView.vue    # 未使用（遗留）
│   │
│   ├── components/          # 组件
│   │   ├── ChatWindow.vue       # 消息列表 + 右键菜单 + 打字机效果
│   │   ├── ChatInput.vue        # 输入区（富功能：文件、语音、自动补全、模型选择）
│   │   ├── MessageBubble.vue    # 消息气泡（用户/助手）
│   │   ├── ToolCallCard.vue     # 工具调用卡片（通用降级组件）
│   │   ├── ToolBubbleRouter.vue # 工具气泡路由（按名选组件）
│   │   ├── SessionSidebar.vue   # 会话侧栏列表 + 悬浮卡片 + 固定卡片
│   │   ├── MemoryPanel.vue      # 记忆面板（Vignette 瀑布流 / Markdown 回退）
│   │   ├── RenderMarkdown.vue   # Markdown 渲染（含沙箱隔离）
│   │   ├── MarkdownEditor.vue   # CodeMirror Markdown 编辑器
│   │   ├── Icon.vue             # SVG 图标组件（内联所有图标）
│   │   ├── ContextMenu.vue      # 右键菜单
│   │   ├── HealthPanel.vue      # 健康状态面板
│   │   ├── ContextUsageBadge.vue # 上下文用量标签
│   │   ├── StatusBadge.vue      # 连接状态点
│   │   ├── TaskTrackerBar.vue   # 任务追踪进度条
│   │   ├── ThinkingBlock.vue    # 思考过程块
│   │   ├── HtmlSandbox.vue      # HTML 沙箱 iframe
│   │   ├── AutocompletePanel.vue # @/#/! 自动补全面板
│   │   ├── ImageThumbnail.vue   # 图片缩略图
│   │   ├── ReferenceChip.vue    # 引用标签
│   │   ├── NewsCard.vue         # 更新动态卡片
│   │   ├── SectionCard.vue      # 记忆分区卡片
│   │   └── MomentCard.vue       # 时刻卡片
│   │
│   ├── components/tools/    # 工具专属气泡组件
│   │   ├── registry.ts          # 工具名→组件 注册表
│   │   ├── _shared/
│   │   │   ├── BubbleChrome.vue     # 气泡骨架（状态图标 + 展开/折叠动画）
│   │   │   ├── displayNames.ts      # 工具名→中文显示名映射
│   │   │   ├── KvTable.vue          # KV 表格
│   │   │   ├── SonettoBlockerError.vue
│   │   │   └── shared.css
│   │   ├── PythonBubble.vue, FilesBubble.vue, FileEditBubble.vue, ...
│   │   ├── TodoBubble.vue + todo/ 子目录
│   │   └── ...
│   │
│   ├── utils/
│   │   ├── references.ts    # 引用解析/序列化（ParsedRef 类型体系）
│   │   ├── markdown.ts      # markdown-it 配置 + 沙箱检测
│   │   └── python-highlight.ts # Python 语法高亮
│   │
│   └── assets/icons/        # SVG 图标（按功能目录组织）
│
├── index.html
├── vite.config.ts           # Vite 配置（API Token 注入 + 代理）
├── tsconfig.json
└── package.json             # Vue 3 + Vue Router + markdown-it + KaTeX + CodeMirror
```

### 技术栈

| 层面 | 选型 | 版本 |
|------|------|------|
| 框架 | Vue 3 (Composition API) | ^3.4.0 |
| 路由 | Vue Router 4 | ^4.3.0 |
| 构建 | Vite 5 | ^5.2.0 |
| 语言 | TypeScript | ^5.4.0 |
| Markdown | markdown-it + texmath + task-lists | 14.x |
| 数学渲染 | KaTeX | 0.16.x |
| 代码编辑 | CodeMirror 6 + vue-codemirror | 6.x |
| 状态管理 | **无 Pinia/Vuex** — 使用模块级 reactive ref | — |

---

## 2. 隐式共享状态模式（核心架构决策）

项目未使用 Pinia 或 Vuex，而是采用了一种**模块级 reactive ref** 模式：

```typescript
// composables/useChat.ts — 模块作用域
const channels = reactive(new Map<string, SessionChannel>())
const turnsCache = loadAllTurnsFromStorage()

export function useChat(sessionId: Ref<string>) {
  // 返回指向 channels 的响应式引用
}
```

```typescript
// composables/useSession.ts — 模块作用域
const sessionId = ref('')
const sessions = ref<SessionInfo[]>([])

export function useSession() {
  // 返回指向 sessionId/sessions 的引用
}
```

**特点：**
- 状态在模块级定义，所有调用 `useXxx()` 的组件共享同一份状态
- 无需 Provider 注入，无 `provide/inject`，无需 Pinia 的安装
- 依赖 `composable` 的 import 时机：先导入的模块会影响后续行为

**潜在问题：**
- 依赖隐式的 import 顺序（`useSession.initIfNeeded()` 在模块级初始化）
- 测试困难：无法为每个测试创建独立隔离的 store 实例
- 缺少 DevTools 支持：无法时间旅行调试

---

## 3. 可引入但未使用的设计模式

### 3.1 观察者/发布-订阅模式（Observer Pattern） — ✅ 已实施

**重构前：** `useChat.ts` 的 `handleEventForChannel` 包含一个 12 路 switch（170 行）和一个 5 段 if-chain（62 行），逐类型处理 WebSocket 事件。

**重构后：** 替换为两张 `Map<EventType, Handler>` 注册表，handler 独立到外部模块：

```
useChat.ts                      # 分发层
├── memoryHandlers.get(type)    # 后台记忆事件 → useChat.memory.ts
└── turnHandlers.get(type)      # 主流程事件   → useChat.handlers.ts
```

```typescript
// useChat.memory.ts — 记忆事件
export type MemoryEventType = 'memory_start' | 'memory_tool_start' | 'memory_tool_end' | 'memory_tool_error' | 'memory_done'
type MemoryEventHandler = (ch: SessionChannel, sid: string, event: ServerEvent) => void

export const memoryHandlers = new Map<MemoryEventType, MemoryEventHandler>([
  ['memory_start', handleMemoryStart],
  ['memory_tool_start', handleMemoryToolStart],
  // ...
])
```

```typescript
// useChat.handlers.ts — 主流程事件
type TurnEventHandler = (ch: SessionChannel, sid: string, turn: ChatTurn, event: ServerEvent) => void

export const turnHandlers = new Map<string, TurnEventHandler>([
  ['thinking_start', handleThinkingStart],
  ['token', handleToken],
  ['tool_start', handleToolStart],
  ['tool_end', handleToolEnd],
  ['done', handleDone],
  // ...
])
```

```typescript
// useChat.ts — 分发
function handleEventForChannel(sid: string, event: ServerEvent) {
  const ch = channels.get(sid)
  // 1. context_usage / sub_session_created → early return
  // 2. memory 事件 → memoryHandlers.get()
  // 3. 主流程事件 → turnHandlers.get()
}
```

**效果：** switch/if-chain → 声明式注册表 + 独立 handler 函数。新增事件类型只需写 handler 函数 + 注册一行，调用方守卫自动覆盖。

**收益：** 每次新增事件类型只需新增一个处理器，switch 不再膨胀。`memory_*` 事件已半独立（`handleMemoryToolEvent` 函数），但没有注册机制。

**实现成本：** 低。重构范围限于 `useChat.ts` 内部。

---

### 3.2 命令模式（Command Pattern）

**现状：** 工具操作通过字符串 + `data` 透传：

```typescript
// ChatView 中
emit('action', { action: 'undo', data: { n: 1 } })

// ChatWindow 中
emit('action', { action: 'user_response', data: { interactionId, response } })
```

**可应用模式：** 定义具名操作对象，使 action 和 data 的关系类型安全：

```typescript
// 理想设计
type ToolAction = 
  | { type: 'undo'; n: number }
  | { type: 'user_response'; interactionId: string; response: string | string[] }
  | { type: 'cite'; ref: ParsedRef }
```

**收益：** 消除 `action` 和 `data` 的魔数字段，获得编译期类型检查。

**实现成本：** 低。纯 TypeScript 类型定义变更。

---

### 3.3 策略模式（Strategy Pattern）— 已有雏形可深化

**现状：** `tools/registry.ts` 和 `ToolBubbleRouter.vue` 已实现简单的策略模式——按工具名选择气泡组件。

```typescript
const registry: Record<string, Component> = {
  'run_python': PythonBubble,
  'tarot': TarotBubble,
  // ...
}
```

**可深化方向：**
1. 每个策略组件可声明自己的 `tooltip`、`icon`、`group` 等元数据（当前 `displayNames.ts` 是平铺映射）
2. 支持动态注册（插件化场景）
3. 对未注册工具的行为可以配置化（默认展开/折叠、最大长度等）

---

### 3.4 工厂模式（Factory Pattern）

**现状：** `ToolBubbleRouter.vue` 使用 `computed` 动态解析组件：

```typescript
const bubbleComponent = computed(() => {
  return getBubbleComponent(props.toolCall.name)
})
```

**可应用模式：** 可考虑「抽象工厂」，按工具分类生产组件。但当前模式的简洁性对项目规模是合适的——**不宜过度设计**。

---

### 3.5 仓库模式（Repository Pattern）

**现状：** `api/index.ts` 是一个扁平对象，40+ 方法。所有 API 调用都在这里。

```typescript
export const api = {
  createSession: () => request<CreateSessionResponse>('/sessions', { method: 'POST' }),
  listSessions: () => request<ListSessionsResponse>('/sessions'),
  listProviders: () => request<ListProvidersResponse>('/providers'),
  // ... 40+ 方法
}
```

**可应用模式：** 按领域拆分：

```typescript
// 理想设计
export const sessionApi = { create, list, get, delete, constify, unconstify }
export const providerApi = { list, get, create, update, delete, test, discover }
export const memoryApi = { getNarrative, getMoment, getMemories }
export const personaApi = { get, update }
```

**收益：** 按领域组织，减少单文件体积（267 行 → 每个文件 30-50 行），增强可发现性。

**实现成本：** 低。纯拆分，不改变接口签名。

---

### 3.6 模板方法模式（Template Method）

**现状：** `PathWhitelistView.vue`、`EnvVarsView.vue`、`SonettoBlockerView.vue` 三者重复相同的「列表/表单切换」模式：

```vue
<template v-if="mode === 'list'">
  <!-- 列表 -->
</template>
<template v-else>
  <!-- 表单 -->
</template>
```

每个的脚本部分有高度相似的：`loading` / `saving` / `formError` ref、`loadXxx()` / `startEdit()` / `cancelForm()` / `handleSave()` 方法。

**可应用模式：** 创建一个通用的 `useCrudForm` composable，封装列表/表单切换逻辑：

```typescript
// 理想设计
function useCrudForm<T>() {
  const mode = ref<'list' | 'form'>('list')
  const loading = ref(false)
  const saving = ref(false)
  const formError = ref('')
  const editingIndex = ref(-1)
  
  function startAdd() { mode.value = 'form'; editingIndex.value = -1 }
  function startEdit(i: number) { mode.value = 'form'; editingIndex.value = i }
  function cancelForm() { mode.value = 'list'; formError.value = '' }
  
  return { mode, loading, saving, formError, editingIndex, startAdd, startEdit, cancelForm }
}
```

**收益：** 消除三个视图组件中约 40% 的重复代码。

**实现成本：** 中。需提取各处差异点（数据加载/保存的具体逻辑不同）。

---

## 4. 难以维护的点

### 4.1 `useChat.ts` — 职能混杂 ⚠️（已部分拆分）

**文件分布：** `useChat.ts` 517 行（原 752）+ `useChat.handlers.ts` 187 行 + `useChat.memory.ts` 89 行。

**仍存在的混杂职责（`useChat.ts`）：**
| 职责 | 行数范围 | 说明 |
|------|---------|------|
| localStorage 持久化 | 10-93 | `saveTurnsToStorage`, `loadAllTurnsFromStorage` |
| WebSocket 连接管理 | 164-228 | `connectSession`, `ensureConnected`, 重连逻辑 |
| 多会话通道管理 | 96-160 | `channels` Map, `getOrCreateChannel` |
| 事件路由（仅分发） | 252-283 | 两张注册表的 `.get()` 分发，无业务逻辑 |
| Turn 状态管理 | 287-433 | `send`, `cancel`, `sendUserResponse`, `removeTurns` |
| 工具查找函数 | 435-517 | `findToolByCallId`, `findBestMatchingTool` 等 |

**已完成的改进：** ✅
- 15 个 handler 函数 → `useChat.memory.ts` / `useChat.handlers.ts`
- 2 张注册表（`memoryHandlers` / `turnHandlers`）随 handler 迁移
- `handleEventForChannel` 从 170 行 switch + 62 行 if-chain → 30 行分发
- `pong` 无操作分支已消除

**仍存在的维护风险：**
- 无法独立测试 WebSocket 重连逻辑（与 localStorage 紧耦合）
- `persistTurns` 仍与模块级 `channels` Map 耦合

### 4.2 `ChatInput.vue` — 900+ 行的巨型组件

**文件大小：** 900+ 行（template 170 行 + script 730 行 + style 630 行）。

**混杂的职责：**
- 文件/文件夹选择器
- 链接粘贴自动识别
- `@`/`#`/`!` 自动补全（技能、工具、宏）
- 语音输入（Web Speech API）— 约 120 行
- Provider/Model 下拉选择器
- 图像认知模式切换
- 发送/停止按钮
- 拖拽调整高度
- 键盘快捷键（全局 Space 长按语音）

**拆分建议：** 至少可拆出 3-4 个独立模块：
- `useVoiceInput` composable（语音识别逻辑）
- `useAutocomplete` composable（@/#/! 补全逻辑）
- `useInputResize` composable（拖拽调整）
- `ProviderSelector` 子组件（模型选择 UI）

### 4.3 隐式共享状态的测试困境

**现状：** 所有 composable 都使用模块级状态：

```typescript
// useChat.ts
const channels = reactive(new Map())
export function useChat(sessionId: Ref<string>) { ... }
```

**问题：**
- 单元测试无法创建隔离的 store 实例
- `useSession.initIfNeeded()` 在模块首次 import 时自动执行，测试无法重置状态
- WebSocket 连接在测试中无法 mock（模块级 `channels` 持有真实连接）

### 4.4 localStorage 作为消息存储

**现状：** 消息历史通过 JSON 序列化存储在 `localStorage`。

**问题：**
- **容量限制：** 约 5-10 MB 上限，长对话可能溢出
- **无索引：** 查找/过滤需反序列化全部数据
- **无迁移策略：** 数据结构变更时，旧数据被静默丢弃（`migrateLegacyTurn` 是手写迁移，每次变更需追加）
- **同步问题：** 多标签页窗口数据不一致
- **性能：** 每次保存全量序列化整个会话

### 4.5 WebSocket 重连逻辑的耦合

`connectSession` 中 `onclose` 设置 3 秒重连：

```typescript
ch.ws.onclose = () => {
  ch.connected = false
  ch.reconnectTimer = setTimeout(() => connectSession(sid), 3000)
}
```

而 `disconnectSession` 为了阻止重连需要手动清除 `onclose`：

```typescript
export function disconnectSession(sid: string) {
  // 先清除 onclose，再手动关闭 WS
  if (ch.ws) {
    ch.ws.onclose = null
    ch.ws.close()
  }
}
```

这种「清除回调再关闭」的模式是脆弱的。如果重连请求已经入队（`setTimeout` 已触发但未执行），则 `disconnectSession` 无效。

### 4.6 CSS 样式不一致

**现状：** 硬编码颜色值散布在组件中：

```css
/* ProvidersView.vue 使用大量硬编码颜色 */
.provider-card { background: #ffffff; }
.card-label { color: #1f2937; }
.card-type-badge { color: #9ca3af; }
.model-tag { color: #6b7280; background: #f3f4f6; }
```

而 `App.vue` 定义了 CSS 变量体系（`--text-primary`, `--text-secondary` 等）。

**问题：** 主题切换时（如果未来实现暗色模式），硬编码颜色的组件无法跟随。目前约 30% 使用 CSS 变量，70% 硬编码。

### 4.7 类型安全的幻影区

多处使用 `as any` 或隐式 `any`：

```typescript
// ChatInput.vue — SpeechRecognition
const recognitionRef = ref<any>(null)

// ChatInput.vue — 路径检查
const entry = refs.value[idx] as any
entry.blocked = true

// useChat.ts — done 事件处理
(event.payload as Record<string, unknown>).turn_id

// ChatInput.vue — pasted link inference
refs.value.push({ type: 'web_link', url: text, label: domain, domain } as ParsedRef)
```

### 4.8 重复的 CRUD 模式

`PathWhitelistView.vue`、`EnvVarsView.vue`、`SonettoBlockerView.vue` 共享几乎相同的模式，但每个文件独立实现：

| 特性 | 各文件重复实现 |
|------|--------------|
| `mode` (list/form) | 3 次 |
| `loading` / `saving` | 3 次 |
| `formError` | 3 次 |
| `cancelForm()` | 3 次 |
| 表单输入字段 | 类似结构 |

### 4.9 `App.vue` — 根组件膨胀

`App.vue` 兼职责：
- 侧栏布局
- 设置菜单弹出
- 服务重启（含 60 次循环探测）
- 会话切换事件处理
- 固定/取消固定会话
- 全局样式定义

根组件应尽量「薄」，将具体业务逻辑委托给子组件或 composable。

### 4.10 动画与逻辑的时间耦合

```typescript
// BubbleChrome.vue
function openBody() {
  bodyWrapper.value.style.maxHeight = h + 'px'
  setTimeout(() => {
    if (bodyWrapper.value && isOpen.value) {
      bodyWrapper.value.style.maxHeight = 'none'
    }
  }, 350)  // ← magic number, 与 CSS transition 0.35s 耦合
}
```

CSS 中 `transition: max-height 0.3s cubic-bezier(...)` 与 JS 中 `350ms` 的时机必须保持一致。修改 CSS 动画时长时必须同步修改 JS。

---

## 5. 改进建议

### 按优先级排序

#### P0 — 影响开发效率

| # | 改进项 | 文件 | 建议 |
|---|--------|------|------|
| 1 | 拆分 `useChat.ts` | `useChat.ts` | 提取 `useWebSocket` (WS 连接/重连)、`useTurnPersistence` (本地存储)、`useEventRouter` (事件分发) |
| 2 | 拆分 `ChatInput.vue` | `ChatInput.vue` | 提取 `useVoiceInput`、`useAutocomplete`、`useInputResize` composable |

#### P1 — 影响代码质量

| # | 改进项 | 涉及文件 | 建议 |
|---|--------|---------|------|
| 3 | 统一 CSS 变量 | 所有 view 组件 | 逐步替换硬编码颜色为 `var(--xxx)` |
| 4 | 提取通用 CRUD composable | `PathWhitelistView`, `EnvVarsView`, `SonettoBlockerView` | 创建 `useCrudForm<T>()` |
| 5 | 引入 Pinia | 全部 composable | 替换模块级 reactive ref，获得 DevTools + 类型安全 + 测试隔离 |
| 6 | 消除 `as any` | 各处 | 使用更精确的类型或类型守卫 |
| 7 | ✅ 事件路由注册化 | `useChat.ts` → `useChat.handlers.ts` + `useChat.memory.ts` | 15 个 handler 已提取为 Map<EventType, Handler> 注册表 + 独立模块 |

#### P2 — 影响可靠性

| # | 改进项 | 涉及文件 | 建议 |
|---|--------|---------|------|
| 8 | 局部存储迁移策略 | `useChat.ts` | 为 `schema_version` 添加 localStorage 校验，自动迁移或优雅降级 |
| 9 | 重连机制解耦 | `useChat.ts` | 使用「请求-确认」模式替代「清除回调再关闭」 |
| 10 | 动画时间常量 | `BubbleChrome.vue`, `ToolCallCard.vue` | 将 CSS transition 时长提取为 CSS 变量，JS 通过 `getComputedStyle` 读取 |

### 推荐重构路线

```
Phase 1（短期，1-2 天）
├── ✅ 事件路由注册化 — handler 已提取到 useChat.{memory,handlers}.ts
├── 拆分 useChat.ts → useWebSocket + useTurnPersistence（剩余部分）
├── 提取 useVoiceInput composable
└── 紧急性 bug 修复

Phase 2（中期，3-5 天）
├── 提取通用 CRUD composable
├── 统一 CSS 变量（逐步替换硬编码颜色）
├── 消除 as any 类型漏洞
└── 引入事件注册机制替代 switch

Phase 3（长期，1-2 周）
├── 引入 Pinia 替代模块级状态
├── 剥离 ChatInput 子组件
├── 建立单元测试框架（Vitest）
└── 动画时间耦合解耦
```

---

## 6. 附录：文件职责速查

### 状态管理文件

| 文件 | 状态类型 | 共享范围 | 持久化方式 |
|------|---------|---------|-----------|
| `composables/useChat.ts` | WebSocket 连接、消息缓存、流式状态 | 全局（模块级 reactive Map） | localStorage |
| `composables/useSession.ts` | 当前 sessionId、会话列表 | 全局（模块级 ref） | localStorage (sessionId) |
| `composables/useHealth.ts` | 健康检查结果 | 全局（模块级 ref） | 无 |
| `composables/useSidebar.ts` | 侧栏折叠状态 | 全局（模块级 ref） | localStorage |

### API 领域分组

| 方法前缀 | 领域 | 方法数 |
|---------|------|--------|
| `createSession/listSessions/...` | 会话管理 | 9 |
| `listProviders/getProvider/...` | 提供商管理 | 11 |
| `listSkills/listTools/listMacros` | 技能/工具发现 | 3 |
| `getPersona/updatePersona` | 人设编辑 | 2 |
| `listWhitelist/addWhitelistEntry/...` | 路径白名单 | 4 |
| `listBlockers/addBlocker/...` | 拒止锚 | 3 |
| `listEnvVars/updateEnvVar/batchUpdateEnvVars` | 环境变量 | 3 |
| `getNarrative/getMoment/getMemories` | 记忆 | 3 |
| 其他（health/restart/balance） | 系统 | 3 |

### 工具气泡注册表（共 38 个工具名 → 15 个组件）

| 组件 | 处理工具 |
|------|---------|
| `TodoBubble` | todo_add/list/complete/uncomplete/delete/update/query... (11) |
| `FilesBubble` | file_read/file_write/file_manage/file_search (4) |
| `MapBubble` | nearby_search/fuzzy_address_search/geocode_address/get_transit_route/get_cycling_route (5) |
| `MemoryBubble` | list/read/create/update/delete/merge_memories (6) |
| `AskUserBubble` | ask_user_*/ask_user_for_info (4) |
| 其余 10 个组件各处理 1 个工具 | |
