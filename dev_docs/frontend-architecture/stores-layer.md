# 状态管理层 — `stores/`

## 层级定位

Pinia 集中状态管理，替代原有的模块级 `reactive(Map)` 和 `ref` 单例。所有模块级可变状态迁移至 Pinia store，状态变更可通过 Vue DevTools 追踪。

```
依赖方向：stores/ 不依赖 composables/ 或 components/
                  被 composables/ 调用
```

## 模块文件清单

| 文件 | Store ID | 核心状态 | 职责 |
|---|---|---|---|
| `sidebarStore.ts` | `sidebar` | `userCollapsed` / `forcedCollapsed` | 侧栏折叠状态 + localStorage 持久化 |
| `healthStore.ts` | `health` | `health: HealthResponse` | 后端健康检查轮询 |
| `sessionStore.ts` | `session` | `sessionId` / `sessions` | 会话 CRUD + localStorage 持久化 |
| `chatStore.ts` | `chat` | `channels: Map<string, SessionChannel>` | WebSocket 连接 + 事件路由 + turn 管理 |

## store 详解

### sidebarStore — 侧栏折叠状态

最简 store，独立的 UI 状态管理：

```typescript
// stores/sidebarStore.ts
export const useSidebarStore = defineStore('sidebar', () => {
  const userCollapsed = ref(false)       // 用户主动折叠偏好
  const forcedCollapsed = ref(false)     // 窄屏（<900px）自动折叠

  // 从 localStorage 恢复用户偏好
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved !== null) userCollapsed.value = saved === 'true'
  } catch { /* 不可用 */ }

  // matchMedia 监听窄屏
  const mql = window.matchMedia('(max-width: 900px)')
  forcedCollapsed.value = mql.matches
  mql.addEventListener('change', (e) => { forcedCollapsed.value = e.matches })

  // 持久化用户偏好
  watch(userCollapsed, (v) => { localStorage.setItem(STORAGE_KEY, String(v)) })

  const effectiveCollapsed = computed(() => userCollapsed.value || forcedCollapsed.value)

  function toggleSidebar() { userCollapsed.value = !userCollapsed.value }

  return { userCollapsed, forcedCollapsed, effectiveCollapsed, toggleSidebar, setUserCollapsed }
})
```

关键设计：
- `effectiveCollapsed` 是 `userCollapsed || forcedCollapsed` 的组合——用户偏好和窄屏自动折叠任一为 true 即生效
- `matchMedia` 监听在 store 初始化时执行一次，后续通过事件驱动更新 `forcedCollapsed`

### healthStore — 健康检查轮询

```typescript
// stores/healthStore.ts
export const useHealthStore = defineStore('health', () => {
  const health = ref<HealthResponse | null>(null)
  let _timer: ReturnType<typeof setInterval> | null = null

  async function refresh() {
    try {
      health.value = await api.health()       // GET /api/health
    } catch {
      health.value = null                      // 连接失败 → null
    }
  }

  function startPolling(intervalMs = 30000) {
    stopPolling()
    refresh()
    _timer = setInterval(refresh, intervalMs)
  }

  function stopPolling() { ... }

  return { health, refresh, startPolling, stopPolling }
})
```

设计要点：
- 默认 30s 轮询间隔
- `refresh()` 失败时将 `health` 置为 `null`，UI 层据此切换连接状态指示
- `stopPolling()` 在 `onUnmounted()` 中调用（通过 composable 层编排）

### sessionStore — 会话管理

```typescript
// stores/sessionStore.ts
export const useSessionStore = defineStore('session', () => {
  const sessionId = ref('')        // 当前活跃会话 ID
  const sessions = ref<SessionInfo[]>([])  // 会话列表

  async function initIfNeeded() {
    // 从 localStorage 恢复 sessionId，若后端不存在则创建新会话
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      try {
        await api.getSession(stored)    // 验证后端存在
        sessionId.value = stored
      } catch {
        await _createSession()           // 不存在 → 创建新会话
      }
    } else {
      await _createSession()
    }
    await refreshSessions()
    cleanupOrphanedCaches()              // 清理孤儿 localStorage 缓存
  }

  async function refreshSessions() {
    sessions.value = (await api.listSessions()).sessions
  }

  async function deleteSession(id: string) {
    await api.deleteSession(id)
    const chatStore = useChatStore()     // 惰性引用，避免循环依赖
    chatStore.disconnectChannel(id)
    localStorage.removeItem(TURNS_KEY_PREFIX + id)
    // 若删除的是当前会话，切换到列表中的第一个或创建新会话
    if (sessionId.value === id) { ... }
  }

  // … createSession, switchSession, constifySession, unconstifySession
})
```

关键设计：
- **惰性引用 `useChatStore()`** — 避免与 `chatStore` 的模块级循环依赖（ESM 运行时通过函数内 import 解决）
- **`cleanupOrphanedCaches()`** — 加载时自动清理后端已不存在的会话的 localStorage 缓存
- **初始化延迟** — `initIfNeeded()` 有 `_initialized` 守卫，确保只执行一次

### chatStore — 聊天核心

最复杂的 store，包含 WebSocket 连接管理、事件路由、turn 生命周期、localStorage 持久化：

```typescript
export const useChatStore = defineStore('chat', () => {
  const channels = reactive(new Map<string, SessionChannel>())
  const turnsCache = loadAllTurnsFromStorage()   // 从 localStorage 恢复

  // ── 计算属性 ──
  const allSessionStatuses = computed(() => { /* 遍历 channels 生成状态快照 */ })

  // ── 通道管理 ──
  function getOrCreateChannel(sid: string): SessionChannel { /* 带缓存恢复 */ }
  function persistTurns(sid: string) { /* 全量写入 localStorage */ }

  // ── WebSocket 生命周期 ──
  function connectSession(sid: string) {
    // 创建 WebSocket → onopen/onclose/onmessage 绑定
    // onclose → 3s 后自动重连
    // onmessage → JSON.parse → handleEventForChannel
  }
  function ensureConnected(sid: string) { /* 惰性连接，已有则跳过 */ }
  function disconnectChannel(sid: string) { /* 关闭 WS + 清理定时器 */ }

  // ── 事件路由 ──
  function handleEventForChannel(sid: string, event: ServerEvent) {
    // 见下方"事件路由优先级"
  }

  // ── 消息发送 ──
  function send(sid, text, refs, ...) { /* 构建 ChatTurn + WS.send */ }
  function cancel(sid) { /* WS.send({type: 'cancel'}) */ }

  return { channels, allSessionStatuses, connectSession, ensureConnected, ... }
})
```

#### SessionChannel 数据结构

```typescript
interface SessionChannel {
  ws: WebSocket | null                    // WebSocket 连接（每个会话独立）
  connected: boolean                      // 是否已连接
  isStreaming: boolean                    // 后端是否正在生成
  isAwaitingUser: boolean                 // 是否等待用户响应（ask_user）
  turns: ChatTurn[]                       // 已完成轮次列表
  currentTurn: ChatTurn | null            // 当前流式轮次
  error: string | null                    // 错误信息
  contextUsage: ContextUsage | null       // 上下文窗口用量
  taskTrackerData: Record<string, unknown> | null
  reconnectTimer: ReturnType<typeof setTimeout> | null
  initialized: boolean
  _awaitingToolName: string | null        // 等待的工具名（ask_user）
  parentSessionId: string | null          // sub-agent 的父会话 ID
  privateMode: boolean
  autoApprove: boolean
}
```

#### 事件路由优先级

`handleEventForChannel()` 有明确的分发顺序，新增事件类型时需注意放置在正确的分支：

```
① context_usage          → 直接设置 ch.contextUsage，无 currentTurn 要求
② sub_session_created    → 异步创建子会话通道、切换会话
③ memory_* 事件           → 通过 turn_id 查找目标 turn，在 currentTurn 守卫之前处理
                          （记忆事件可能在 done 之后到达，此时 currentTurn 已清空）
④ thinking_start/token/… → 需要 currentTurn 存在，通过 turnHandlers 查表调用
   answer/done/error/ask_user
```

## 与旧架构的对比

| 维度 | 旧架构（模块级单例） | 新架构（Pinia store） |
|---|---|---|
| 状态定义 | `const refs = reactive(new Map())` | `defineStore('id', () => { ... })` |
| 状态追踪 | 无（DevTools 不可见） | Vue DevTools Pinia 面板可见 |
| 循环依赖 | `useChat.ts` ↔ `useSession.ts` | 通过惰性 `useChatStore()` 调用消除 |
| 响应式解构 | 直接 `const { x } = useXxx()` | 需 `storeToRefs(store)` 保持 ref 包装 |
| SSR 兼容 | 否（模块级 ref 跨请求泄漏） | 是（每次请求独立 store 实例） |

## 关键设计要点

### 1. storeToRefs 是必须的

Pinia store 实例自动 unwrap 所有 ref——`store.sessionId` 返回 `string` 而非 `Ref<string>`。在 composable 封装层必须使用 `storeToRefs(store)` 来保留 ref 包装：

```typescript
// ❌ 错误：失去响应性
export function useSidebar() {
  return { collapsed: useSidebarStore().collapsed }

// ✅ 正确：保持响应式绑定
export function useSidebar() {
  const { collapsed } = storeToRefs(useSidebarStore())
  return { collapsed }
}
```

### 2. Chat event handlers 保持独立文件

事件处理函数（`useChat.handlers.ts` 和 `useChat.memory.ts`）没有被移入 store 文件，而是保持独立。原因：

- **文件体积控制** — `chatStore.ts` 已承担 WebSocket 生命周期 + 事件路由 + 消息发送，加入所有处理器逻辑会膨胀到 ~800 行
- **关注点分离** — handlers 是纯函数（输入 `(ch, turn, event)` → 副作用），便于单独测试
- **注册表模式** — `handlers.ts` 导出 `Map<string, TurnEventHandler>`，新增事件类型只需在注册表中添加条目

### 3. channels 使用 reactive(Map)

`channels` 使用 `reactive(new Map<string, SessionChannel>())` 而非 `Record<string, SessionChannel>`：

- Vue 3 的 `reactive()` 对 `Map` 有完整支持（`.get()` `.set()` `.delete()` 均有依赖追踪）
- 会话 ID 作为 key 是动态增删的，Map 比对象更适合这种场景
- 遍历 `channels` 时 `.forEach()` 和 `for...of` 均被响应式追踪

### 4. localStorage 作为读缓存

`turnsCache` 在 store 初始化时从 localStorage 全量加载，之后 `getOrCreateChannel()` 自动恢复缓存数据：

```
页面加载 → loadAllTurnsFromStorage() → turnsCache Map
  ↓
ensureConnected(sid) → getOrCreateChannel(sid)
  → turnsCache.has(sid) ? 恢复 turns : 空数组
  ↓
轮次完成 → persistTurns(sid) → JSON.stringify → localStorage.setItem
```
