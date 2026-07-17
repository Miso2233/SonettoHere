# WebSocket 数据流

## 连接生命周期

### 连接建立

```
会话创建/切换
  ↓
useChat(sessionId) — watch(sessionId, { immediate: true })
  ↓
chatStore.ensureConnected(sid)
  ↓
getOrCreateChannel(sid) ← 从 localStorage 恢复缓存 turns
  ↓ (首次初始化)
connectSession(sid)
  ↓
new WebSocket(`ws://${host}/ws/chat/${sid}`, [authToken])
 ↓      ↓        ↓
onopen  onmessage  onclose
```

### 断线重连

```
WebSocket 意外关闭
  ↓
ch.ws.onclose
  ↓
ch.connected = false
ch.reconnectTimer = setTimeout(() => connectSession(sid), 3000)
  ↓ (3s 后)
connectSession(sid) — 创建新 WebSocket
  ↓
onopen → clearTimeout(reconnectTimer)
```

### 连接断开（主动）

```
chatStore.disconnectChannel(sid)
  ↓
clearTimeout(reconnectTimer)   ← 防止重连
ch.ws.onclose = null           ← 阻止 onclose 触发意外重连
ch.ws.close()
ch.ws = null
ch.connected = false
ch.initialized = false
channels.delete(sid)           ← 完全移除通道
```

## 消息协议

### 客户端 → 服务端

| type | payload | 用途 |
|---|---|---|
| `chat` | `{ message, private?, auto_approve?, provider_id?, model_name?, image_recognition?, image_refs? }` | 发送用户消息 |
| `cancel` | `{}` | 取消当前生成 |
| `ping` | `{}` | WebSocket 心跳 |
| `user_response` | `{ interaction_id, response }` | 用户对 ask_user 的响应 |
| `update_auto_approve` | `{ auto_approve: boolean }` | 更新自动执行模式 |

### 服务端 → 客户端（ServerEvent 联合类型）

#### 聊天轮次事件（按推送顺序）

| type | payload | handler |
|---|---|---|
| `thinking_start` | `{ timestamp }` | `handleThinkingStart` — 压入 ThinkingBlock |
| `token` | `{ token: string }` | `handleToken` — 追加到 lastThink.tokens |
| `thinking_end` | `{ timestamp }` | `handleThinkingEnd` — lastThink.done = true |
| `tool_start` | `{ call_id, tool_name, input }` | `handleToolStart` — 压入 running ToolCall |
| `tool_end` | `{ call_id, tool_name, output, elapsed, tool_data? }` | `handleToolEnd` — 更新 ToolCall 为 done |
| `tool_error` | `{ call_id, tool_name, error }` | `handleToolError` — 更新为 error |
| `answer` | `{ content }` | `handleAnswer` — 设置 finalAnswer + becameAnswer |
| `done` | `{ turn_id?, context_usage? }` | `handleDone` — 轮次 finalize + 持久化 |

#### 元事件（可在轮次外到达）

| type | payload | 处理方式 |
|---|---|---|
| `context_usage` | `{ current_tokens, max_tokens, usage_percent, model_name, breakdown? }` | 直接设置 ch.contextUsage，不依赖 currentTurn |
| `error` | `{ code, message }` | `handleError` — 设置 ch.error，清除流式状态 |
| `pong` | `{}` | 心跳响应，忽略（客户端无需处理） |
| `ask_user` | `{ tool_name, question, mode, options, interaction_id, code? }` | `handleAskUser` — 设置交互等待状态 |
| `sub_session_created` | `{ sub_session_id, parent_session_id, task, name }` | 动态导入 sessionStore → 创建子会话 → 切换 |

#### 记忆层事件（后台独立，通过 turn_id 关联）

| type | payload | 处理方式 |
|---|---|---|
| `memory_start` | `{ turn_id }` | 压入「处理中」占位条目 |
| `memory_tool_start` | `{ turn_id, tool_name, input }` | 压入 running 记忆工具事件 |
| `memory_tool_end` | `{ turn_id, tool_name, output, elapsed }` | 更新为 done |
| `memory_tool_error` | `{ turn_id, tool_name, error }` | 更新为 error |
| `memory_done` | `{ turn_id }` | 移除占位，无实际修改时渲染 memory_review |

## Token 流式渲染时间线

```
time ──────────────────────────────────────────────►

WS:     thinking_start  token×N  thinking_end  answer  done
         │                │        │           │       │
UI:      ThinkingBlock    tokens   标题折叠    became  persist
         创建并显示       实时追加  spinner 消失 Answer   到 turns
                                    样式切换 设置       刷新列表
```

### 关键时序细节

1. **thinking_start 立即响应** — 收到事件即创建 ThinkingBlock，用户立即看到"思考中…"状态
2. **token 逐字追加** — 每个 token 事件触发 `lastThink.tokens += token`，Vue 响应式驱动 `RenderMarkdown` 重渲染
3. **thinking_end 视觉切换** — `done = true` 触发 CSS 过渡：spinner 消失、标题折叠、背景切换为气泡样式
4. **answer 标记转化** — `becameAnswer = true` 标记 ThinkingBlock 的内容已转化为最终答案
5. **done 延迟持久化** — `becameAnswer` 分支延迟 420ms 后再将 turn 从 currentTurn 推入 completed turns，给 iframe 渲染留出时间窗口

## 事件处理优先级

WebSocket 事件按以下优先级在 `handleEventForChannel()` 中分发：

```
1. context_usage       优先级最高，无需轮次上下文
2. sub_session_created 需立即创建子会话通道和切换会话
3. memory_* 事件       在 currentTurn 守卫之前处理（可在 done 之后到达）
4. 其他所有事件        需 currentTurn 存在，通过 turnHandlers Map 分发
```

这一优先级设计避免了以下竞态条件：

- **记忆事件时序问题**：后台记忆 consumer 是独立任务，可能在 `done` 事件之后才完成。`memory_*` 事件使用 `turn_id` 查找目标 turn，而非依赖 `ch.currentTurn`
- **sub_session_created**：需要在切换会话前完成子会话通道创建，否则事件到达时目标会话尚无 currentTurn
