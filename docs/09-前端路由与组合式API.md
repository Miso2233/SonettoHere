# 前端路由与组合式 API

## 为什么需要路由？

传统的多页网站，每次点击链接浏览器都会刷新整个页面，从服务器重新加载 HTML。这种方式慢且用户体验差。

现代 SPA（Single Page Application）使用**前端路由**解决这个问题：URL 变化时，不刷新整个页面，只替换页面中的内容区域。Vue Router 就是 Vue 生态中实现前端路由的标准库。

本项目的路由只定义了两个页面：

```
URL          组件              用途
/            ChatView.vue      主聊天界面
/memory      MemoryView.vue    长期记忆查看
```

---

## Vue Router 配置

[`web/src/router/index.ts`](../web/src/router/index.ts)：

```typescript
import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '@/views/ChatView.vue'
import MemoryView from '@/views/MemoryView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'chat', component: ChatView },
    { path: '/memory', name: 'memory', component: MemoryView },
  ],
})

export default router
```

### 逐行解析

**`createWebHistory()`**：使用浏览器的 History API（`pushState`/`popState`）。URL 看起来是正常的（`/memory`），没有 `#` 符号。需要后端配合——所有未知路径都要返回 `index.html`（本项目的 FastAPI 在 `server.py` 中配置了 `StaticFiles(html=True)` 自动处理此事）。

**`routes` 数组**：每个路由对象包含三要素：

| 字段 | 含义 | 示例 |
|------|------|------|
| `path` | URL 匹配路径 | `/memory` |
| `name` | 路由名称（可选，便于代码中引用） | `'memory'` |
| `component` | 匹配时渲染的 Vue 组件 | `MemoryView` |

### 路由如何挂载到应用

[`web/src/main.ts`](../web/src/main.ts)：

```typescript
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(router)        // ← 安装 Vue Router 插件
app.mount('#app')      // ← 挂载到 index.html 中的 <div id="app">
```

三步：`createApp` 创建应用 → `app.use(router)` 安装路由 → `app.mount('#app')` 挂载到 DOM。

---

## router-link 与 router-view

这两个组件是 Vue Router 提供的"开箱即用"组件。

### router-link：导航链接

在 `App.vue` 的侧边栏中：

```vue
<nav class="sidebar-nav">
  <router-link to="/" class="nav-item">对话</router-link>
  <router-link to="/memory" class="nav-item">记忆</router-link>
</nav>
```

`router-link` 渲染为 `<a>` 标签，但它**不会**触发页面刷新。当用户点击时，Vue Router 拦截点击事件，更新 URL，然后只替换 `<router-view>` 中的内容。

`router-link` 还有一个重要特性：当前活跃的路由链接会自动获得 `router-link-active` 类名。本项目利用这一点高亮侧边栏当前项：

```css
.nav-item.router-link-active {
  background: var(--bg-card);
  color: var(--accent);
  font-weight: 600;
}
```

### router-view：内容渲染出口

在 `App.vue` 的 `<main>` 区域：

```vue
<main class="main">
  <router-view />
</main>
```

当 URL 为 `/` 时，`<router-view>` 渲染 `ChatView.vue`；当 URL 为 `/memory` 时，渲染 `MemoryView.vue`。侧边栏保持不变——只有 `<router-view>` 的内容在变化。

### 路由切换时的组件生命周期

当用户从 `/` 导航到 `/memory`：
1. `ChatView.vue` 被**卸载**（`onUnmounted` 触发）
2. `MemoryView.vue` 被**挂载**（`onMounted` 触发）

这意味着 `ChatView` 中的 WebSocket 连接会被关闭（`onUnmounted` 调用了 `disconnect()`），而 `MemoryView` 挂载后会调用 `refresh()` 获取最新记忆。

---

## 组合式 API（Composables）模式

Vue 2 时代，复杂的逻辑常用 Vuex 或 Pinia 做状态管理。Vue 3 引入了 **Composables** 模式——将可复用的有状态逻辑提取为独立函数，用文件名 `useXxx` 命名。

本项目的两个 composables 替代了传统状态管理库的角色：

### 文件级单例模式

观察 `useSession.ts` 的结构：

```typescript
import { ref } from 'vue'

// ★ 模块级变量 — 所有调用者共享同一个实例
const sessionId = ref('')
const sessions = ref<SessionInfo[]>([])
let _initialized = false

// ★ 导出的函数 — 每次都返回同一份状态引用
export function useSession() {
  initIfNeeded()
  return { sessionId, sessions, createSession, switchSession, deleteSession, refreshSessions }
}
```

注意：`sessionId` 和 `sessions` 定义在函数**外部**。这意味着无论 `useSession()` 被调用多少次（比如在 `App.vue` 和 `ChatView.vue` 中各调用一次），它们访问的都是**同一个** `sessionId` 和 `sessions`。

这被称为"文件级单例模式"——一个 `.ts` 文件就是一个天然的状态容器。不需要 Pinia、不需要 Vuex，Vue 的 `ref`/`reactive` 本身就能做到。

### useChat 也如此

```typescript
export function useChat(sessionId: Ref<string>) {
  const ws = ref<WebSocket | null>(null)
  const connected = ref(false)
  // ...
  return { connected, isStreaming, turns, currentTurn, error, send, cancel, connect, disconnect }
}
```

与 `useSession` 不同的是，`useChat` 接收一个参数 `sessionId`——当 session 变化时，它会自动断开旧 WebSocket、清空消息、连接到新 session。这个参数是响应式的——`watch(sessionId, ...)` 确保了切换会话时的自动重连。

### Composable 的职责边界

| Composable | 管理什么 | 用什么通信 |
|-----------|---------|-----------|
| `useSession` | 会话列表、当前会话 ID、localStorage 持久化 | REST API |
| `useChat` | WebSocket 连接、消息轮次、流式 token 组装 | WebSocket |

两者之间有清晰的协作关系：`useSession` 提供 `sessionId`，`useChat` 消费 `sessionId`。

```
App.vue
  │
  ├── useSession()  →  sessionId, sessions, createSession, switchSession, deleteSession
  │
  └── ChatView.vue
        │
        ├── useSession()  →  复用同一个 sessionId（文件级单例）
        │
        └── useChat(sessionId)  →  connected, turns, currentTurn, send, cancel
                                 →  当 sessionId 变化时自动重连
```

---

## useChat 源码深度剖析

`useChat` 是项目中最复杂也最重要的 composable，约 170 行。我们从初始化到消息收发逐一拆解。

### 连接建立（connect 函数）

```typescript
function connect() {
  if (ws.value?.readyState === WebSocket.OPEN) return  // 已连接则跳过

  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${protocol}//${location.host}/ws/chat/${sessionId.value}`

  ws.value = new WebSocket(url)

  ws.value.onopen = () => {
    connected.value = true
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  ws.value.onclose = () => {
    connected.value = false
    reconnectTimer = setTimeout(connect, 3000)  // 3 秒后自动重连
  }

  ws.value.onmessage = (event) => {
    const msg: ServerEvent = JSON.parse(event.data)
    handleEvent(msg)
  }
}
```

关键点：
- `location.protocol === 'https:' ? 'wss:' : 'ws:'`：自动匹配当前页面的协议
- `reconnectTimer = setTimeout(connect, 3000)`：断线后 3 秒自动重连——生产级的弹性设计
- `JSON.parse(event.data)` 后交给 `handleEvent` 统一分发

### 消息发送（send 函数）

```typescript
function send(message: string) {
  if (!ws.value || ws.value.readyState !== WebSocket.OPEN) return
  isStreaming.value = true
  error.value = null

  const turn: ChatTurn = {
    id: crypto.randomUUID(),    // 生成唯一回合 ID
    userMessage: message,
    thinking: [],               // LLM 思考块列表（初始为空）
    toolCalls: [],              // 工具调用记录（初始为空）
    finalAnswer: null,          // 最终回答（初始为空）
  }
  currentTurn.value = turn      // 开始新的当前回合

  const payload: ClientMessage = { type: 'chat', payload: { message } }
  ws.value.send(JSON.stringify(payload))
}
```

`crypto.randomUUID()` 是浏览器原生 API——生成类似 `a3f1c8e2-...` 的唯一标识符，用于前端跟踪回合。

### 事件分发（handleEvent 函数）

这是整个前端最核心的函数——它将后端推送的 JSON 事件转换为 UI 状态更新：

```typescript
function handleEvent(event: ServerEvent) {
  const turn = currentTurn.value
  if (!turn) return

  switch (event.type) {

    case 'thinking_start':
      turn.thinking.push({ tokens: '', done: false })
      break

    case 'token':
      // 将 token 追加到最后一个思考块的 tokens 中
      if (turn.thinking.length > 0) {
        const last = turn.thinking[turn.thinking.length - 1]
        last.tokens += event.payload.token
      }
      break

    case 'thinking_end':
      if (turn.thinking.length > 0) {
        turn.thinking[turn.thinking.length - 1].done = true
      }
      break

    case 'tool_start': {
      const tc: ToolCall = {
        name: event.payload.tool_name,
        input: event.payload.input,
        output: null,
        elapsed: null,
        status: 'running',        // 开始时状态为 running
      }
      turn.toolCalls.push(tc)
      break
    }

    case 'tool_end': {
      const tc = findRunningTool(turn.toolCalls, event.payload.tool_name)
      if (tc) {
        tc.output = event.payload.output
        tc.elapsed = event.payload.elapsed
        tc.status = 'done'        // 结束时改为 done
      }
      break
    }

    case 'answer':
      turn.finalAnswer = event.payload.content
      break

    case 'done':
      // 将当前回合归档到已完成的 turns 数组
      if (currentTurn.value) {
        turns.push(currentTurn.value)
        currentTurn.value = null
      }
      isStreaming.value = false
      break

    case 'error':
      error.value = event.payload.message
      isStreaming.value = false
      break

    case 'pong':
      break  // 心跳响应，无需处理
  }
}
```

每个 `case` 都很简洁——接收到类型对应的事件，更新响应式状态，Vue 自动处理 UI 更新。没有复杂的中间层次。

### 会话切换自动重连

```typescript
watch(
  sessionId,
  () => {
    disconnect()          // 断开旧连接
    turns.splice(0)       // 清空消息列表
    currentTurn.value = null
    error.value = null
    if (sessionId.value) {
      connect()           // 连接新会话
    }
  },
  { immediate: true }     // 初始化时立即执行
)
```

`watch` 是 Vue 的"观察者"——当 `sessionId` 引用变化时，自动执行回调。`{ immediate: true }` 表示组件挂载时立即执行一次（即初始连接）。

### 辅助函数：findRunningTool

```typescript
function findRunningTool(toolCalls: ToolCall[], toolName: string): ToolCall | undefined {
  // 从后往前找，匹配同名且状态为 running 的工具
  for (let i = toolCalls.length - 1; i >= 0; i--) {
    if (toolCalls[i].name === toolName && toolCalls[i].status === 'running') {
      return toolCalls[i]
    }
  }
  return undefined
}
```

为什么从后往前找？同一个工具可能在同一次思考中被多次调用（比如重复查询）。从后往前确保匹配到最新一个状态为 `running` 的同名工具。

---

## useSession 源码深度剖析

`useSession` 管理会话 CRUD，同时处理 localStorage 持久化和错误恢复。

### 初始化流程

```typescript
async function initIfNeeded() {
  if (_initialized) return
  _initialized = true

  const stored = localStorage.getItem(STORAGE_KEY)  // 读取上次的会话 ID
  if (stored) {
    try {
      await api.getSession(stored)  // 验证会话是否仍存在
      sessionId.value = stored      // 存在 → 恢复
    } catch {
      await _createSession()        // 不存在 → 创建新会话
    }
  } else {
    await _createSession()          // 无记录 → 创建新会话
  }
  await refreshSessions()
}
```

逻辑树：
```
localStorage 有存储的 ID？
  ├── 是 → 调用 GET /api/sessions/{id}
  │         ├── 成功 → 恢复该会话
  │         └── 404 → 创建新会话
  └── 否 → 创建新会话
            ↓
        刷新会话列表
```

这种模式叫"乐观恢复"——优先尝试恢复上次的会话，失败则透明地创建新的。

### 会话删除

```typescript
async function deleteSession(id: string) {
  await api.deleteSession(id)
  if (sessionId.value === id) {
    // 正在删除当前活动会话
    await refreshSessions()
    if (sessions.value.length > 0) {
      await switchSession(sessions.value[0].session_id)  // 切换到第一个
    } else {
      await createSession()  // 全删完了，创建全新会话
    }
  } else {
    await refreshSessions()
  }
}
```

删除后自动切换到另一个会话，确保用户始终有一个活动会话。这种细致的状态处理让用户体验流畅。

---

## Composable 模式 vs 传统状态管理

| 对比维度 | 本项目 (Composables) | Pinia / Vuex |
|---------|---------------------|--------------|
| 安装 | 无需额外依赖 | 需要安装 pinia |
| 学习成本 | Vue 3 自带 API | 需学 Pinia 的 store/actions/getters 概念 |
| 代码量 | 很少 | 需要定义 store 结构 |
| TypeScript 支持 | 天然支持 | 良好 |
| DevTools 集成 | 仅 Vue DevTools | 有专用面板 |
| 适用场景 | 中小型应用、教学项目 | 大型应用、团队协作 |

本项目选择 composable 模式的关键原因：**用最少的概念讲清楚状态管理**。`ref` + `reactive` + `watch` 全部是 Vue 3 自带 API，初学者不需要额外学习状态管理库。

---

## 小结

通过本章，你学到了：

1. **Vue Router**：`createWebHistory`、`routes`、`router-link`、`router-view`
2. **Composable 模式**：文件级单例、`useXxx` 命名约定、状态逻辑与 UI 分离
3. **`useChat` 内部**：WebSocket 连接/断开/重连、事件分发、回合生命周期
4. **`useSession` 内部**：localStorage 持久化、乐观恢复、错误处理

下一章将详细拆解 REST API 客户端，以及前端如何使用 TypeScript 类型安全地调用后端 API。

---

← [Vue 3 组件树与响应式数据流](08-Vue3组件树与响应式数据流.md) | [REST API 与前后端数据交互](10-REST与前后端数据交互.md) →
