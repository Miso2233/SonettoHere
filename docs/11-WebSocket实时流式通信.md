# WebSocket 实时流式通信

## 为什么需要 WebSocket？

HTTP 是无状态、请求-响应模式的协议。客户端发一个请求，服务器回一个响应，通信结束。但聊天应用需要：

1. **服务器主动推送**：AI 的回复不是瞬间生成的，LLM 逐 token 输出，服务器需要持续推送 token 到前端
2. **长连接**：一次对话可能持续很久，不能每个 token 都重新建立 HTTP 连接
3. **双向通信**：用户可以随时点"停止"按钮中断生成

WebSocket 完美匹配这些需求：它在客户端和服务器之间建立一条**持久双向通道**，两端可以随时向对方发送消息，无需等待请求-响应周期。

---

## WebSocket 协议速览

HTTP 和 WebSocket 的对比：

```
HTTP:
  客户端 ──GET /api/sessions──→ 服务器
  客户端 ←──200 { sessions: [...] }── 服务器
  （连接关闭）

WebSocket:
  客户端 ──Upgrade 握手──→ 服务器
  ════════ 持久连接建立 ════════
  客户端 ──{ type: "chat" }──→ 服务器
  服务器 ←──{ type: "thinking_start" }── 客户端
  服务器 ←──{ type: "token", payload: { token: "今" } }── 客户端
  服务器 ←──{ type: "token", payload: { token: "天" } }── 客户端
  客户端 ──{ type: "cancel" }──→ 服务器
  服务器 ←──{ type: "error", payload: { code: "CANCELLED" } }── 客户端
  （连接保持，等待下一条 chat 消息）
```

WebSocket 的 URL 以 `ws://`（或加密的 `wss://`）开头，而非 `http://`。

---

## 前端 WebSocket 连接管理

[`web/src/composables/useChat.ts`](../web/src/composables/useChat.ts) 中的 `connect` 函数：

```typescript
function connect() {
  if (ws.value?.readyState === WebSocket.OPEN) return  // 防止重复连接

  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${protocol}//${location.host}/ws/chat/${sessionId.value}`

  ws.value = new WebSocket(url)

  ws.value.onopen = () => {
    connected.value = true
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

### WebSocket 状态机

浏览器的 `WebSocket` 对象有四种就绪状态：

| 常量 | 值 | 含义 |
|------|----|------|
| `WebSocket.CONNECTING` | 0 | 正在建立连接 |
| `WebSocket.OPEN` | 1 | 连接已建立，可以收发消息 |
| `WebSocket.CLOSING` | 2 | 正在关闭连接 |
| `WebSocket.CLOSED` | 3 | 连接已关闭 |

`connect()` 函数开头的 `if (ws.value?.readyState === WebSocket.OPEN) return` 防止在已连接的情况下重复建立连接。

### 自动重连机制

```typescript
ws.value.onclose = () => {
  connected.value = false
  reconnectTimer = setTimeout(connect, 3000)  // 3 秒后重试
}
```

重连是自动的——用户不需要手动点"重新连接"。3 秒的延迟避免了后端重启时的大量无效连接尝试。

当用户主动切换会话时，`disconnect()` 会先清除 `reconnectTimer`，避免旧会话的重连干扰：

```typescript
function disconnect() {
  if (reconnectTimer) {
    clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  ws.value?.close()
  ws.value = null
  connected.value = false
}
```

---

## 通信协议：结构化 JSON 消息

前后端之间流通的不是原始文本，而是**类型明确的结构化 JSON**。

### 客户端 → 服务器（两种消息）

```typescript
// types/index.ts
export interface ChatMessage {
  type: 'chat'
  payload: { message: string }
}

export interface CancelMessage {
  type: 'cancel'
  payload: Record<string, never>   // 空对象
}

export type ClientMessage = ChatMessage | CancelMessage
```

发送聊天消息：

```typescript
function send(message: string) {
  const payload: ClientMessage = { type: 'chat', payload: { message } }
  ws.value.send(JSON.stringify(payload))
}
```

发送取消指令：

```typescript
function cancel() {
  const payload: ClientMessage = { type: 'cancel', payload: {} }
  ws.value.send(JSON.stringify(payload))
}
```

### 服务器 → 客户端（10 种事件）

每种事件都有专属的 TypeScript 接口。完整的事件流：

```
用户发送 "帮我查一下北京天气"

服务端推送序列：
  ① { type: "thinking_start",  payload: { timestamp: 1715432000.5 } }
  ② { type: "token",           payload: { token: "好的" } }
  ③ { type: "token",           payload: { token: "，" } }
  ④ { type: "token",           payload: { token: "我来" } }
     ...（持续推 token）...
  ⑤ { type: "thinking_end",    payload: { timestamp: 1715432001.2 } }
  ⑥ { type: "tool_start",      payload: { tool_name: "get_current_weather", input: '{"city":"北京"}' } }
  ⑦ { type: "tool_end",        payload: { tool_name: "get_current_weather", output: "北京今天晴，25°C...", elapsed: 0.83 } }
  ⑧ { type: "thinking_start",  payload: { timestamp: 1715432002.5 } }
     ...（第二轮思考的 token）...
  ⑨ { type: "thinking_end",    payload: { timestamp: 1715432003.0 } }
  ⑩ { type: "answer",          payload: { content: "北京今天天气晴朗，气温约25°C……" } }
  ⑪ { type: "done",            payload: { turn_id: "a3f1c8e2..." } }
```

这个序列完美展示了 ReAct Agent 的 Thought → Action → Observation → Answer 循环在 UI 层面的体现。

---

## handleEvent：将事件流转换为 UI 更新

```typescript
function handleEvent(event: ServerEvent) {
  const turn = currentTurn.value
  if (!turn) return

  switch (event.type) {
    case 'thinking_start':
      // 开始一个新的思考块
      turn.thinking.push({ tokens: '', done: false })
      break

    case 'token':
      // token 追加到当前思考块的末尾
      if (turn.thinking.length > 0) {
        const last = turn.thinking[turn.thinking.length - 1]
        last.tokens += event.payload.token
      }
      break

    case 'thinking_end':
      // 标记当前思考块完成
      if (turn.thinking.length > 0) {
        turn.thinking[turn.thinking.length - 1].done = true
      }
      break

    case 'tool_start':
      // 新建一个工具调用记录
      turn.toolCalls.push({
        name: event.payload.tool_name,
        input: event.payload.input,
        output: null,
        elapsed: null,
        status: 'running',
      })
      break

    case 'tool_end':
      // 更新对应工具调用的结果
      const tc = findRunningTool(turn.toolCalls, event.payload.tool_name)
      if (tc) {
        tc.output = event.payload.output
        tc.elapsed = event.payload.elapsed
        tc.status = 'done'
      }
      break

    case 'answer':
      // Agent 的最终回答
      turn.finalAnswer = event.payload.content
      break

    case 'done':
      // 回合结束：归档到 turns，清空 currentTurn
      if (currentTurn.value) {
        turns.push(currentTurn.value)
        currentTurn.value = null
      }
      isStreaming.value = false
      break

    case 'error':
      // 错误处理（含取消）
      error.value = event.payload.message
      isStreaming.value = false
      break
  }
}
```

### 关键设计：响应式局部更新

`handleEvent` 不重新渲染整个聊天窗口——它只修改 `turn` 对象上的具体属性。Vue 的响应式系统确保只有**受影响**的 DOM 节点被更新：

- `thinking_end` → 只有 `ThinkingBlock.vue` 重新渲染（移除旋转动画，变灰）
- `tool_end` → 只有对应的 `ToolCallCard.vue` 重新渲染（显示耗时和结果）
- `answer` → 只有 `MessageBubble.vue` 重新渲染

这种"精确更新"是 Vue 响应式系统的天然优势——不需要手动 diff，不需要虚拟 DOM 操作，声明式地描述数据与 UI 的关系即可。

---

## 取消机制：前端→后端→前端

取消是双向实时通信中最复杂的场景之一。本项目用了 asyncio 的 `Task.cancel()` 机制：

### 前端发送取消

```typescript
function cancel() {
  const payload: ClientMessage = { type: 'cancel', payload: {} }
  ws.value.send(JSON.stringify(payload))
}
```

### ChatInput 中的停止按钮

```vue
<button v-if="!isStreaming" @click="handleSend">发送</button>
<button v-else @click="$emit('stop')">停止</button>
```

`isStreaming` 状态控制按钮切换：发送中显示红色"停止"按钮，空闲时显示金色"发送"按钮。

### 后端处理取消（`api/routes/chat.py`）

```python
elif msg_type == "cancel":
    if session._active_task:
        session._active_task.cancel()  # ← asyncio 取消正在执行的 Agent 任务
```

### 取消后的前端状态

```python
# 后端被取消后进入 except 块
except asyncio.CancelledError:
    await ws.send_json({
        "type": "error",
        "payload": {"code": "CANCELLED", "message": "生成已取消"},
    })
finally:
    session._active_task = None
    await ws.send_json({
        "type": "done",
        "payload": {"turn_id": turn_id},
    })
```

前端收到 `error` 事件后设置 `error.value`，继续收到 `done` 事件后归档当前回合。取消不会丢失已生成的内容——`thinking` 和 `toolCalls` 正常显示，只是 `finalAnswer` 可能不完整。

---

## 后端 WebSocket 回调层

前端看到的所有事件，都源于后端 `WebSocketCallback` 类（[`api/callbacks/websocket_callback.py`](../api/callbacks/websocket_callback.py)）。

### 它与 LangChain 回调的集成

`WebSocketCallback` 继承 `BaseCallbackHandler`，实现了 LangChain 生命周期钩子：

```python
class WebSocketCallback(BaseCallbackHandler):
    def __init__(self, ws: WebSocket):
        self._ws = ws
        self._thinking_started = False
        self._tool_start_time: dict[str, float] = {}
        self._tool_names: dict[str, str] = {}

    async def on_llm_start(self, ...):
        # LLM 开始推理 → 通知前端显示"思考中"动画
        await self._ws.send_json({
            "type": "thinking_start",
            "payload": {"timestamp": time.time()},
        })

    async def on_llm_new_token(self, token: str, ...):
        # LLM 输出一个 token → 通知前端追加到思考块
        await self._ws.send_json({
            "type": "token",
            "payload": {"token": token},
        })

    async def on_tool_start(self, serialized, input_str, ...):
        # 工具开始执行 → 记录开始时间，通知前端
        run_id = str(kwargs.get("run_id", ""))
        self._tool_start_time[run_id] = time.time()
        await self._ws.send_json({
            "type": "tool_start",
            "payload": {"tool_name": tool_name, "input": input_str},
        })

    async def on_tool_end(self, output, ...):
        # 工具执行完成 → 计算耗时，通知前端展示结果
        elapsed = time.time() - self._tool_start_time.pop(run_id, time.time())
        await self._ws.send_json({
            "type": "tool_end",
            "payload": {"tool_name": tool_name, "output": out_str, "elapsed": round(elapsed, 2)},
        })
```

### 回调被如何注入 Agent 图

在 `chat.py` 中：

```python
config = {
    "configurable": {"thread_id": session_id},
    "callbacks": [ws_callback],  # ← 将 WebSocket 回调注入 LangGraph
}

async for event in graph.astream_events(inputs, config=config, version="v2"):
    # astream_events 在每次 LLM 调用/工具执行时触发 WebSocketCallback
```

`astream_events` 是 LangGraph 的流式事件 API。它生成的事件还会触发 `config["callbacks"]` 中注册的回调——从而驱动 WebSocket 事件流。

### 对比：CLI 版回调 vs Web 版回调

| 对比维度 | `PrinterCallback`（CLI） | `WebSocketCallback`（Web） |
|---------|-------------------------|---------------------------|
| 输出目标 | 终端（`print`） | 浏览器（`ws.send_json`） |
| 输出格式 | 彩色 ANSI 文本 | 结构化 JSON |
| 事件语义 | 视觉装饰（┌── [Thinking]） | 机器可读（`type: "thinking_start"`） |
| 可复用性 | 仅供 CLI | 可供任何 Web 客户端 |

两者实现了相同模式（LangChain `BaseCallbackHandler`），但适配到不同的输出通道。这正是回调模式的价值——核心逻辑（Agent）与输出通道（CLI/Web）完全解耦。

---

## 聊天流程完整时序图

```
┌─ 浏览器 ─┐                          ┌─ FastAPI ─┐
│ ChatInput │                          │ chat.py   │
│  发送消息  │── {type:"chat"} ──────→│            │
│            │                          │ 构建 Agent 图
│            │                          │ 注入 WebSocketCallback
│            │                          │
│            │←── {type:"thinking_start"} ──│  LLM 开始推理
│  显示转圈  │                          │
│            │←── {type:"token":"好"} ──│  LLM 输出 token
│            │←── {type:"token":"的"} ──│
│            │←── {type:"token":"，"} ──│
│  逐字显示  │                          │
│            │←── {type:"thinking_end"} ──│  LLM 推理结束
│            │                          │
│            │←── {type:"tool_start"} ──│  工具开始执行
│  显示工具  │                          │
│            │←── {type:"tool_end"}   ──│  工具执行完成
│  显示结果  │                          │
│            │                          │
│            │←── {type:"thinking_start"} ──│  第二轮推理
│            │←── ... tokens ...       ──│
│            │←── {type:"thinking_end"} ──│
│            │                          │
│            │←── {type:"answer"}      ──│  最终回答
│  显示回答  │                          │
│            │←── {type:"done"}        ──│  回合结束
│  降级归档  │                          │
│            │                          │  写入短期记忆
│            │                          │  送入长期记忆队列
└────────────┘                          └────────────┘
```

---

## 小结

通过本章，你学到了：

1. **WebSocket 原理**：持久双向连接，对比 HTTP 请求-响应模式
2. **连接管理**：状态机、自动重连、会话切换时的清理逻辑
3. **事件协议**：10 种服务器 → 客户端事件，2 种客户端 → 服务器消息
4. **handleEvent**：将 JSON 事件映射到 Vue 响应式状态更新
5. **取消机制**：前端发送 cancel → asyncio 取消 Task → 后端回传 error + done
6. **WebSocketCallback**：LangChain 回调如何桥接到 WebSocket 协议

下一章将介绍开发模式和生产模式的差异，以及前端如何通过 Vite 构建为可以部署的静态文件。

---

← [REST API 与前后端数据交互](10-REST与前后端数据交互.md) | [从开发到生产：前端工程化](12-从开发到生产：前端工程化.md) →
