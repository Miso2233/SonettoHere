# 组合式层 — `composables/`

## 层级定位

**业务逻辑编排层**，负责将 Pinia store 的原始状态和 actions 转换为组件可用的响应式 API，以及处理与 store 无关的纯函数逻辑。

```
依赖方向：composables/ → stores/ (调用 useXxxStore)
                    → api/ (发起 HTTP 请求)
                    → types/ (使用 TS 类型)
                    → utils/ (使用工具函数)
```

## 模块文件清单

| 文件 | 核心导出 | 职责 |
|---|---|---|
| `useChat.ts` | `useChat(sessionId)` 、工具函数 | **聊天核心 orchestration**：WS 事件处理、turn 生命周期 |
| `useChat.handlers.ts` | `turnHandlers` Map | 事件处理器注册表：9 种 WS 事件的 handler |
| `useChat.memory.ts` | `memoryHandlers` Map | 记忆层事件处理器：5 种 memory 事件的 handler |
| `useSession.ts` | `useSession()` 、模块级函数 | 会话管理编排，委托 sessionStore |
| `useHealth.ts` | `useHealth()` 、`health` ref | 健康检查编排，委托 healthStore |
| `useSidebar.ts` | `useSidebar()` | 侧栏状态编排，委托 sidebarStore |

## 关键文件详解

### useChat.ts — 聊天核心编排

**定位**：为 `ChatView.vue` 提供聊天所需的全部响应式状态和操作 API。

```typescript
export function useChat(sessionId: Ref<string>) {
  const store = useChatStore()

  // 根据当前 sessionId 查找对应通道
  const activeChannelRef = computed(() => store.getOrCreateChannel(sessionId.value))

  // 暴露给组件的响应式属性（全部委托到 activeChannelRef）
  const connected = computed(() => activeChannelRef.value.connected)
  const isStreaming = computed(() => activeChannelRef.value.isStreaming)
  const turns = computed(() => activeChannelRef.value.turns)
  const currentTurn = computed(() => activeChannelRef.value.currentTurn)
  // … error, contextUsage, taskTrackerData, privateMode, autoApprove

  // Session 切换时自动持久化 + 确保 WS 连接
  watch(sessionId, (newId, oldId) => {
    if (oldId) store.persistTurns(oldId)
    store.ensureConnected(newId)
  }, { immediate: true })

  // UI 操作委托
  function send(text, refs, ...) { store.send(sessionId.value, text, refs, ...) }
  function cancel() { store.cancel(sessionId.value) }
  // … sendUserResponse, removeTurns, setPrivateMode, setAutoApprove

  return { connected, isStreaming, turns, currentTurn, … }
}
```

**工具函数导出**（纯函数，不依赖 store 实例）：

| 函数 | 用途 |
|---|---|
| `findLastThinking(events)` | 从 events 数组反向查找最后一个 thinking 块 |
| `findToolByCallId(events, callId)` | 通过 callId 精确匹配 ToolCall |
| `findBestMatchingTool(events, toolName)` | 三级降级匹配 ToolCall |
| `findFirstRunningToolForInteraction(events, toolName)` | 查找首个未分配 interaction 的 running tool |
| `findTurnByBackendId(ch, turnId)` | 通过后端 turn_id 查找 turn（currentTurn → turns） |
| `findRunningMemoryTool(events, toolName)` | 在 memoryEvents 中查找 running 状态工具 |

### useChat.handlers.ts — 事件处理器注册表

**核心模式**：Map 注册表 + 纯函数处理器。

```typescript
type TurnEventHandler = (ch: SessionChannel, sid: string, turn: ChatTurn, event: ServerEvent) => void

export const turnHandlers = new Map<string, TurnEventHandler>([
  ['thinking_start', handleThinkingStart],   // 压入 ThinkingBlock
  ['token',           handleToken],           // 追加 token 到 lastThink.tokens
  ['thinking_end',   handleThinkingEnd],      // lastThink.done = true
  ['tool_start',     handleToolStart],        // 压入 running ToolCall
  ['tool_end',       handleToolEnd],          // 更新 ToolCall 为 done
  ['tool_error',     handleToolError],        // 更新 ToolCall 为 error
  ['answer',         handleAnswer],           // 设置 finalAnswer + becameAnswer
  ['done',           handleDone],             // 轮次 finalize + 持久化
  ['error',          handleError],            // 设置错误信息
  ['ask_user',       handleAskUser],          // 设置交互等待状态
])
```

**handleToken** — 最频繁调用的 handler：

```typescript
function handleToken(ch, _sid, turn, event) {
  const lastThink = findLastThinking(turn.events)   // O(n) 反向查找
  if (lastThink) {
    lastThink.tokens += (event as TokenEvent).payload.token  // 字符串追加
  }
}
```

**handleDone** — 最复杂的 handler，控制 turn 生命周期终结：

```
handleDone 执行顺序：
  ① 清除 isAwaitingUser / _awaitingToolName
  ② 存储 context_usage / turn_id
  ③ 判断 becameAnswer 分支：
     ├── true → 延迟 420ms 后 push 到 ch.turns（等待 AnswerBlock iframe 渲染完成）
     └── false → 立即 push 到 ch.turns
  ④ ch.currentTurn = null, ch.isStreaming = false
  ⑤ 非私密模式 → persistTurns(sid) 写入 localStorage
  ⑥ refreshSessions() → 更新会话列表 message_count
  ⑦ 子 Agent 完成 → 500ms 后 switchSession 回父会话
```

### useChat.memory.ts — 记忆层事件处理器

```typescript
export const memoryHandlers = new Map<MemoryEventType, MemoryEventHandler>([
  ['memory_start',       handleMemoryStart],       // 压入「处理中」占位
  ['memory_tool_start',  handleMemoryToolStart],    // 压入 running CRUD 事件
  ['memory_tool_end',    handleMemoryToolEnd],      // 更新为 done + 持久化
  ['memory_tool_error',  handleMemoryToolError],    // 更新为 error + 持久化
  ['memory_done',        handleMemoryDone],         // 移除占位，渲染 memory_review
])
```

特殊设计：
- `read_memories` 纯读取操作被 `skipReadMemories()` 过滤，前端不显示
- 消费完成但无任何 CRUD 工具调用时，插入 `memory_review` 占位条目（显示为"记忆检查：无需修改"）

### useSession.ts / useHealth.ts / useSidebar.ts

这三个文件已简化为 Pinia store 的薄封装：

```typescript
// 标准模式
export function useSession() {
  const store = useSessionStore()
  store.initIfNeeded()
  const { sessionId, sessions } = storeToRefs(store)   // storeToRefs 保持响应性
  return { sessionId, sessions, createSession: store.createSession, … }
}

// 模块级函数（向后兼容）
export const refreshSessions = () => useSessionStore().refreshSessions()
export const switchSession = (id: string) => useSessionStore().switchSession(id)
```

## 设计要点

### 1. Composables 只编排，不管理状态

Composables 不持有自己的 `ref()`/`reactive()` 状态，全部委托到 Pinia store。组件的 `useXxx()` 调用在每次组件实例化时创建新的编排上下文，但所有状态共享同一 store 单例。

### 2. handlers 的依赖注入

Handlers 不直接调用 store，而是通过函数参数注入 `(ch, sid, turn, event)`：

```typescript
// handlers 是纯函数 —— 所有的可变状态通过参数传入
function handleToken(ch: SessionChannel, _sid: string, turn: ChatTurn, event: ServerEvent)
```

这样做的好处：
- Handlers 可以被独立测试（mock channel/turn/event 即可）
- Handlers 不依赖 store 的存在（不影响 Pinia 安装时序）
- 同一 handler 可被用于不同的 store 实现（理论上的可替换性）

### 3. 向后兼容的模块级导出

迁移到 Pinia 的过程中，通过模块级函数保持外部接口不变：

```typescript
// 旧代码（消费者）：import { disconnectSession } from '@/composables/useChat'
// 新代码（composable 内部）：
export function disconnectSession(sid: string) {
  useChatStore().disconnectChannel(sid)    // 委托到 store
}
```

这些兼容导出将在外部组件全部迁移后移除。
