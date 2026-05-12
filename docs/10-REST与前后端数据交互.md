# REST API 与前后端数据交互

## 什么是 REST API？

REST（Representational State Transfer）是一套 HTTP API 设计规范。它的核心思想是：**用 URL 定位资源，用 HTTP 方法表达操作意图**。

| HTTP 方法 | 语义 | 对应数据库操作 | 示例 |
|-----------|------|---------------|------|
| `GET` | 读取 | Read | `GET /api/sessions` — 获取会话列表 |
| `POST` | 创建 | Create | `POST /api/sessions` — 创建新会话 |
| `DELETE` | 删除 | Delete | `DELETE /api/sessions/{id}` — 删除会话 |

本项目只用了这三种方法（不需要更新接口，所以没有 PUT/PATCH）。

后端通过 FastAPI 提供 5 个 REST 端点，前端通过 `fetch` API 调用它们。

---

## 前端 API 客户端总览

[`web/src/api/index.ts`](../web/src/api/index.ts) 只有 36 行，但展示了生产级 API 客户端的所有关键要素：

```typescript
import type {
  CreateSessionResponse,
  ListSessionsResponse,
  SessionInfo,
  NarrativeResponse,
} from '@/types'

const BASE = '/api'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    throw new Error(`API ${url} 返回 ${res.status}`)
  }
  return res.json()
}

export const api = {
  createSession: () =>
    request<CreateSessionResponse>('/sessions', { method: 'POST' }),

  listSessions: () =>
    request<ListSessionsResponse>('/sessions'),

  getSession: (id: string) =>
    request<SessionInfo>(`/sessions/${id}`),

  deleteSession: (id: string) =>
    request<{ status: string }>(`/sessions/${id}`, { method: 'DELETE' }),

  getNarrative: () =>
    request<NarrativeResponse>('/narrative'),
}
```

---

## 逐层解析

### 第一层：泛型请求函数

```typescript
async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    throw new Error(`API ${url} 返回 ${res.status}`)
  }
  return res.json()
}
```

逐行分析：

- **`<T>` 泛型参数**：调用者告诉这个函数"我期望返回什么类型"。例如 `request<CreateSessionResponse>` 表示返回值是 `Promise<CreateSessionResponse>`。TypeScript 编译器会确保调用者按照这个类型使用返回值。
- **`fetch()`**：浏览器原生 HTTP 请求 API。第一个参数是 URL，第二个参数是配置对象。
- **`headers: { 'Content-Type': 'application/json' }`**：告诉后端"我发送的是 JSON 格式"。
- **`...options`**：调用者传入的额外配置（如 `method: 'POST'`）合并进来。
- **`if (!res.ok)`**：`res.ok` 只在状态码为 200-299 时为 `true`。404、500 等情况会抛异常。
- **`return res.json()`**：将响应体解析为 JSON 对象，类型为 `T`。

为什么单独抽出一个 `request` 函数？**DRY 原则（Don't Repeat Yourself）**。如果 5 个 API 调用各自写一遍 `fetch` + `headers` + 错误检查 + `res.json()`，代码量会膨胀 5 倍，而且修改公共逻辑需要改 5 处。

### 第二层：语义化 API 方法

```typescript
export const api = {
  createSession: () =>
    request<CreateSessionResponse>('/sessions', { method: 'POST' }),

  listSessions: () =>
    request<ListSessionsResponse>('/sessions'),
  // ...
}
```

每个方法名直接对应业务意图（`createSession`、`listSessions`）。调用者不需要知道 URL 是什么、用什么 HTTP 方法——只需 `api.createSession()`。

### 为什么不引入 axios？

axios 是最流行的 HTTP 客户端库，但本项目刻意不用它。原因：

| 维度 | `fetch`（本项目） | `axios` |
|------|------------------|---------|
| 依赖 | 浏览器内置，零依赖 | 需安装 `axios` 包 |
| API 风格 | Promise-based，`res.json()` 手动解析 | 自动 JSON 解析 |
| 错误处理 | 只看网络错误，HTTP 错误需手动 `res.ok` | 自动抛异常 |
| 拦截器 | 无（但也不需要） | 有 request/response 拦截器 |
| 学习价值 | 理解浏览器底层机制 | 快速开发 |

对于教学项目，"理解底层"比"方便"更重要。`fetch` 是每个前端开发者必须掌握的浏览器 API。

---

## 类型安全的 API 调用

TypeScript 的类型系统是本项目的第一道质量防线。API 调用者和 API 提供者（后端）通过类型定义形成契约。

### 类型定义（契约）

```typescript
// types/index.ts
export interface CreateSessionResponse {
  session_id: string
  created_at: number
}

export interface SessionInfo {
  session_id: string
  message_count: number
  created_at: number
  last_active?: number
}

export interface ListSessionsResponse {
  sessions: SessionInfo[]
}
```

### 类型消费（执行契约）

在 `useSession.ts` 中调用时，TypeScript 自动提供类型检查：

```typescript
const res = await api.createSession()
//    ^? CreateSessionResponse — TypeScript 自动推导

sessionId.value = res.session_id  // ✅ 类型匹配
sessionId.value = res.foo         // ❌ 编译报错：foo 不存在于 CreateSessionResponse
```

如果后端改了返回格式（比如把 `session_id` 改名为 `id`），TypeScript 编译就会失败，开发者会在编辑器中立即看到错误，而不是等到运行时才发现。

---

## 五个 API 端点的完整调用链

### 1. 创建会话

```
用户点击侧边栏 "+" 按钮
    │
    ▼
SessionSidebar emit('create')
    │
    ▼
App.vue → useSession.createSession()
    │
    ▼
api.createSession()  →  fetch POST /api/sessions
    │
    ▼
后端 sessions.py
    │  sm = request.app.state.session_manager
    │  session = sm.create()
    │  return {"session_id": "...", "created_at": ...}
    │
    ▼
前端接收: { session_id: "abc123", created_at: 1715432000 }
    │
    ├── sessionId.value = "abc123"    → 触发 useChat 重连到新会话
    ├── localStorage.setItem()       → 持久化会话 ID
    └── refreshSessions()            → 更新侧边栏会话列表
```

### 2. 刷新会话列表

```typescript
async function refreshSessions() {
  try {
    const res = await api.listSessions()
    sessions.value = res.sessions  // 更新侧边栏
  } catch {
    sessions.value = []            // 失败则清空（不阻断用户操作）
  }
}
```

`try/catch` 确保即使后端挂了，前端也不会崩溃——侧边栏显示空列表，但聊天功能不受影响（聊天走 WebSocket，不依赖 REST）。

### 3. 验证并恢复会话

页面首次加载时：

```typescript
const stored = localStorage.getItem('sonetto_session_id')
if (stored) {
  try {
    await api.getSession(stored)  // GET /api/sessions/{id}
    sessionId.value = stored      // 后端确认会话存在 → 恢复
  } catch {
    await _createSession()        // 404 → 创建新会话
  }
}
```

这是一个优雅的恢复流程——优先找回上次的会话，失败则静默创建新会话。用户感知不到这个过程的复杂性。

### 4. 删除会话

```typescript
await api.deleteSession(id)       // DELETE /api/sessions/{id}
if (sessionId.value === id) {
  // 删的是当前活跃会话 → 自动切换到第一个
  if (sessions.value.length > 0) {
    await switchSession(sessions.value[0].session_id)
  } else {
    await createSession()
  }
}
```

### 5. 获取长期记忆

`MemoryPanel.vue` 在挂载时调用：

```typescript
onMounted(() => refresh())

async function refresh() {
  const res = await api.getNarrative()
  narrative.value = res.narrative    // Markdown 文本
}

// 然后用 marked 库渲染：
const rendered = computed(() => {
  return marked.parse(narrative.value || '') as string
})
```

`computed` 是 Vue 的计算属性——当 `narrative.value` 变化时，`rendered` 会自动重新计算，触发 DOM 更新。

---

## 请求的发起时机总结

| 时机 | 调用 | 触发组件 |
|------|------|---------|
| 页面首次加载 | `initIfNeeded()` → 恢复或创建会话 | `useSession`（模块级 auto-init） |
| 页面首次加载 | `refreshSessions()` | `useSession` |
| 用户点 "+" | `createSession()` | `SessionSidebar` |
| 用户点会话名 | `switchSession(id)` | `SessionSidebar` |
| 用户点 × | `deleteSession(id)` | `SessionSidebar` |
| 进入 /memory 页面 | `getNarrative()` | `MemoryPanel.onMounted()` |
| 用户点"刷新" | `getNarrative()` | `MemoryPanel` |

注意：聊天消息的发送和接收**不经过这里**——它们走 WebSocket。REST 只负责"辅助数据"（会话信息、记忆文本），WebSocket 负责"核心功能"（实时对话）。

---

## 后端对应的路由定义

前端的每个 `fetch` 调用都对应后端的一个 FastAPI 路由：

### 会话 CRUD（`api/routes/sessions.py`）

```python
@router.post("/sessions")
async def create_session(request: Request):
    sm = request.app.state.session_manager
    session = sm.create()
    return {"session_id": session.session_id, "created_at": session.created_at}

@router.get("/sessions")
async def list_sessions(request: Request):
    sm = request.app.state.session_manager
    return {"sessions": sm.list_sessions()}

@router.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request):
    sm = request.app.state.session_manager
    session = sm.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return { ... }

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, request: Request):
    sm = request.app.state.session_manager
    if not sm.delete(session_id):
        raise HTTPException(status_code=404)
    return {"status": "deleted"}
```

### 记忆读取（`api/routes/memory.py`）

```python
@router.get("/narrative")
async def get_narrative(request: Request):
    ltm = request.app.state.ltm
    return {"narrative": ltm.get_narrative()}
```

关键观察：
- 后端路由的返回格式与前端的 TypeScript 类型定义**一一对应**
- `request.app.state.session_manager` 是 FastAPI 的 `app.state` 机制——在应用启动时创建，所有请求共享
- 后端使用 Pydantic 模型做参数校验（`session_id: str`）

---

## 错误处理策略

本项目的错误处理遵循"静默降级"原则：

```typescript
// useSession.ts
async function refreshSessions() {
  try {
    const res = await api.listSessions()
    sessions.value = res.sessions
  } catch {
    sessions.value = []  // ← 失败不清空旧数据，只显示空列表
    // 不弹窗、不报错、不阻断用户操作
  }
}
```

```typescript
// MemoryPanel.vue
async function refresh() {
  loading.value = true
  try {
    const res = await api.getNarrative()
    narrative.value = res.narrative
  } catch {
    narrative.value = ''  // ← 静默失败
  } finally {
    loading.value = false
  }
}
```

"静默降级"意味着核心功能（聊天）不受辅助功能（会话列表、记忆读取）的 API 失败影响。WebSocket 连接独立于 REST，即使 REST API 全部挂掉，用户依然可以正常聊天。

---

## 小结

通过本章，你学到了：

1. **REST 设计规范**：URL 定位资源，HTTP 方法表达操作
2. **泛型请求封装**：`request<T>()` 模式，一次封装到处复用
3. **TypeScript 类型契约**：前端类型与后端返回格式一一对应
4. **五个 API 的完整调用链**：从用户点击到后端响应
5. **静默降级**：辅助功能失败不影响核心聊天功能

下一章将深入 WebSocket——如何实现实时、双向、流式的 AI 对话。

---

← [前端路由与组合式 API](09-前端路由与组合式API.md) | [WebSocket 实时流式通信](11-WebSocket实时流式通信.md) →
