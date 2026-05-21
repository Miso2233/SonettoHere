# 前后端通信方式

## 概述

SonettoHere Web 端采用 **REST + WebSocket 双通道**通信架构：

- **REST API**：会话 CRUD、记忆查询、文件操作等请求-响应式操作
- **WebSocket**：流式 Agent 对话、实时 tool call 推送、ask_user 交互

后端基于 FastAPI，前端基于 Vue 3 + TypeScript。

---

## REST API

基础路径：`/api`

### 会话管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/sessions` | 创建新会话 |
| `GET` | `/sessions` | 列出所有会话 |
| `GET` | `/sessions/{id}` | 获取单个会话信息 |
| `GET` | `/sessions/{id}/messages` | 获取会话消息历史 |
| `GET` | `/sessions/{id}/context-usage` | 获取上下文用量估算 |
| `DELETE` | `/sessions/{id}` | 删除会话 |

**请求/响应示例：**

```jsonc
// POST /sessions
// → { "session_id": "a1b2c3...", "created_at": 1715000000.0 }

// GET /sessions
// → {
//     "sessions": [
//       {
//         "session_id": "a1b2c3...",
//         "message_count": 5,
//         "created_at": 1715000000.0,
//         "last_active": 1715000100.0,
//         "has_active_agent": false   // 该会话是否有正在运行的 Agent
//       }
//     ]
//   }

// GET /sessions/{id}
// → { "session_id": "a1b2c3...", "message_count": 5, "created_at": 1715000000.0, "has_active_agent": false }

// GET /sessions/{id}/messages
// → { "session_id": "a1b2c3...", "messages": [{ "role": "user", "content": "你好" }, { "role": "assistant", "content": "你好！" }] }

// GET /sessions/{id}/context-usage
// → { "current_tokens": 1520, "max_tokens": 8192, "usage_percent": 18.6, "model_name": "deepseek-v4-flash", "session_id": "a1b2c3..." }

// DELETE /sessions/{id}
// → { "status": "deleted" }
```

### 记忆

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/narrative` | 获取长期记忆叙事（MEMORY.md 全文） |

```jsonc
// GET /narrative
// → { "narrative": "## 用户信息\n..." }
```

### 文件

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/select-file` | 打开系统文件选择对话框（参数 `type: "file" | "folder"`） |
| `GET` | `/file` | 读取文件内容（参数 `path`，含路径穿越防护） |

```jsonc
// GET /select-file?type=file
// → { "path": "C:/Users/.../file.txt" }   // 用户取消则 path 为 null

// GET /file?path=./README.md
// → FileResponse (文件二进制内容)
```

### 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 服务健康检查 |

```jsonc
// GET /health
// → { "status": "ok", "version": "1.0.0" }
```

---

## WebSocket 协议

### 连接

```
ws[s]://<host>/ws/chat/{session_id}
```

连接建立后，服务端立即推送初始 `context_usage` 事件。随后进入双工通信循环。

### 客户端 → 服务端消息

所有消息均为 JSON 格式，包含 `type` 和 `payload` 字段：

| type | payload | 触发时机 |
|------|---------|---------|
| `"chat"` | `{ "message": string }` | 用户发送对话消息 |
| `"cancel"` | `{}` | 用户取消当前生成 |
| `"ping"` | `{}` | 心跳保活 |
| `"user_response"` | `{ "interaction_id": string, "response": string \| string[] }` | 用户回复 ask_user 交互 |

```jsonc
// → { "type": "chat",          "payload": { "message": "北京的天气怎么样？" } }
// → { "type": "cancel",        "payload": {} }
// → { "type": "ping",          "payload": {} }
// → { "type": "user_response", "payload": { "interaction_id": "abc123", "response": "海淀区" } }
```

### 服务端 → 客户端事件

单轮对话中事件按以下顺序推送：

```
context_usage (仅连接时)
  → thinking_start → token* → thinking_end
  → (tool_start → tool_end/tool_error)*
  → (ask_user → 等待用户回复)*
  → answer
  → done (含 context_usage)
```

| type | payload | 说明 |
|------|---------|------|
| `"context_usage"` | `{ current_tokens, max_tokens, usage_percent, model_name }` | 连接时推送初始值，done 事件中附最终值 |
| `"thinking_start"` | `{ timestamp }` | LLM 开始生成 |
| `"token"` | `{ token: string }` | 流式 token |
| `"thinking_end"` | `{ timestamp }` | LLM 生成结束 |
| `"tool_start"` | `{ tool_name, input }` | 工具开始执行（input 截断至 500 字符） |
| `"tool_end"` | `{ tool_name, output, elapsed, tool_data? }` | 工具执行完成（output 截断至 300 字符，tool_data 为结构化结果） |
| `"tool_error"` | `{ tool_name, error }` | 工具执行出错 |
| `"ask_user"` | `{ tool_name, question, mode, options, interaction_id }` | Agent 向用户提问 |
| `"answer"` | `{ content }` | Agent 最终回答 |
| `"done"` | `{ context_usage? }` | 本轮对话完成 |
| `"error"` | `{ code, message }` | 任务取消或异常 |
| `"pong"` | `{}` | 心跳回复 |

```jsonc
// ← { "type": "context_usage", "payload": { "current_tokens": 120, "max_tokens": 8192, "usage_percent": 1.5, "model_name": "deepseek-v4-flash" } }
// ← { "type": "thinking_start", "payload": { "timestamp": 1715000000 } }
// ← { "type": "token",          "payload": { "token": "北京" } }
// ← { "type": "token",          "payload": { "token": "的" } }
// ← { "type": "thinking_end",   "payload": { "timestamp": 1715000001 } }
// ← { "type": "tool_start",     "payload": { "tool_name": "get_current_weather", "input": "北京" } }
// ← { "type": "tool_end",       "payload": { "tool_name": "get_current_weather", "output": "晴 22°C", "elapsed": 0.8, "tool_data": { "city": "北京", "temp": "22" } } }
// ← { "type": "answer",         "payload": { "content": "北京今天晴，22°C。" } }
// ← { "type": "done",           "payload": { "context_usage": { "current_tokens": 350, "max_tokens": 8192, "usage_percent": 4.3, "model_name": "deepseek-v4-flash" } } }
```

### tool_data 结构化输出

`tool_end` 事件的 `tool_data` 字段由服务端 `tool_extractors.py` 根据工具名称注册的提取器生成，前端通过 [ToolBubbleRouter](web/src/components/ToolBubbleRouter.vue) 路由到对应的气泡组件渲染。常见的 tool_data 结构：

| 工具 | tool_data 结构 |
|------|---------------|
| `get_current_weather` | `{ city, temp, condition, humidity, wind }` |
| `todo_list` | `{ tool_type: "task_list", total, tasks: [...] }` |
| `nearby_search` | `{ count, pois: [...], location }` |
| `run_python` | `{ tool_type: "run_python", stdout, code }` |
| `smart_search` | `{ query, total_results, results: [...], sources }` |
| ... | 详见 [tool_extractors.py](api/callbacks/tool_extractors.py) |

---

## 多会话通道架构

前端使用 **多通道（Multi-Channel）** 架构管理 WebSocket 连接，每个 Session 拥有独立的通信通道。

### SessionChannel

```typescript
interface SessionChannel {
  ws: WebSocket | null          // 该会话的 WebSocket 连接
  connected: boolean             // 连接状态
  isStreaming: boolean           // 是否正在流式生成
  turns: ChatTurn[]             // 已完成的对话轮次
  currentTurn: ChatTurn | null  // 当前正在进行的轮次
  error: string | null
  contextUsage: ContextUsage | null
  reconnectTimer: ReturnType<typeof setTimeout> | null  // 断线重连定时器
  initialized: boolean          // 是否已初始化
}
```

所有通道存储在模块级 `Map<string, SessionChannel>` 中（[useChat.ts](web/src/composables/useChat.ts#L64)）。

### 连接管理

- **惰性连接**：只有当 Session 被切换为"活跃"状态时才建立 WebSocket 连接
- **断线重连**：连接断开后自动以 3 秒间隔重连
- **不中断切换**：切换活跃 Session 时，原 Session 的 WebSocket **不断开**，后台 Agent 持续运行并接收事件
- **显式清理**：删除 Session 时调用 `disconnectSession()` 关闭对应 WebSocket

```
Page Load → 切换 Session A
  → ensureConnected('session-a')
    → 建立 ws://host/ws/chat/session-a
    → 开始接收事件，存入 Session A 的 Channel

用户切换到 Session B（Session A 的 WS 保持打开）
  → ensureConnected('session-b')
    → 建立 ws://host/ws/chat/session-b
    → Session A 的 Agent 持续运行，事件继续写入 Session A 的 Channel

用户切回 Session A
  → 直接显示 Session A Channel 中的 turns（包含后台完成的新数据）
```

### 事件路由

所有 WebSocket 事件通过 `handleEventForChannel(sid, event)` 路由到对应 Session 的 Channel，操作该 Channel 的 `turns` 和 `currentTurn`，与前端的计算属性联动。

---

## ask_user 交互机制

Agent 在需要用户输入时（如询问确认、选择选项），通过 **Future + WebSocket** 模式实现同步等待：

```
Agent 调用 ask_user_qa / ask_user_single_choice / ask_user_multi_choice
  │
  ├─ 服务端：register() → 创建 Future，存入 _pending 字典
  ├─ 服务端：发送 "ask_user" WS 事件 → 前端
  │
  ├─ 前端：AskUserBubble 渲染表单
  │
  └─ 用户提交 →
      前端发送 "user_response" WS 事件
        → 服务端 resolve() → Future set_result()
          → Agent 继续执行
```

- 超时时间：300 秒
- 取消：Agent 任务取消时 `asyncio.CancelledError` 被捕获，清理 Future

---

## Context Usage 计算

基于 `tiktoken` 的 `cl100k_base` 编码器：

```python
estimate_context_usage(messages, system_prompt, max_tokens, model_name)
  → { current_tokens, max_tokens, usage_percent, model_name }
```

计算公式：

```text
current_tokens = system_prompt_token_count
               + sum(count_tokens(m.content) for m in messages)
               + 4 * len(messages)    # 每条消息的开销
```

计算时机：

1. **WebSocket 连接建立时**：基于空消息列表（尚无 graph 执行）
2. **每轮对话结束时**：基于 Graph Checkpointer 的完整状态（含 tool call/result）估算，随 `done` 事件推送
3. **REST API**：`GET /sessions/{id}/context-usage`，基于 Graph Checkpointer 状态

---

## 关键文件索引

| 文件 | 内容 |
|------|------|
| [api/server.py](api/server.py) | FastAPI 工厂、路由挂载、CORS、静态文件 |
| [api/routes/sessions.py](api/routes/sessions.py) | REST 会话 CRUD |
| [api/routes/memory.py](api/routes/memory.py) | 记忆 API |
| [api/routes/files.py](api/routes/files.py) | 文件选择/读取 API |
| [api/routes/chat.py](api/routes/chat.py) | WebSocket 端点、Agent 执行 |
| [api/session_manager.py](api/session_manager.py) | 会话状态管理 |
| [api/interaction.py](api/interaction.py) | ask_user 交互 Future 注册表 |
| [api/context_usage.py](api/context_usage.py) | Token 用量估算 |
| [api/callbacks/websocket_callback.py](api/callbacks/websocket_callback.py) | LangGraph → WS 事件翻译 |
| [api/callbacks/tool_extractors.py](api/callbacks/tool_extractors.py) | 工具结构化数据提取 |
| [web/src/types/index.ts](web/src/types/index.ts) | TypeScript 类型定义 |
| [web/src/api/index.ts](web/src/api/index.ts) | REST 客户端 |
| [web/src/composables/useChat.ts](web/src/composables/useChat.ts) | WebSocket 多通道管理 |
| [web/src/composables/useSession.ts](web/src/composables/useSession.ts) | 会话生命周期编排 |
| [web/src/components/tools/AskUserBubble.vue](web/src/components/tools/AskUserBubble.vue) | 用户交互表单 |
