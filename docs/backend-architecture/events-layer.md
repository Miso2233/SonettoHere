# 事件发送层 (api/events/)

## 层级定位

**横向基础设施层**，负责后端所有 WebSocket 事件发送的统一封装与错误处理。

不归属于纵向的 7 层分层体系，而是被多个层级共同使用。所有 Sender 通过 `interaction.current_ws` ContextVar 隐式获取 WebSocket 引用（记忆层除外——使用 `from_session_id` 从 `session_manager` 查找）。

```
                          interaction.current_ws (ContextVar)
                                   │
              ┌────────────────────┼─────────────────────┐
              ▼                    ▼                     ▼
       ChatSender           TurnSender             CallbackSender
       (路由层)              (Agent 层)              (回调层)              MemorySender
              │                    │                     │               (记忆层: 从
              └────────────────────┼─────────────────────┘            session_manager
                                   ▼                                    查找 ws)
                            api/events/
                     (WsTransport 基类 + 5 个语义 Sender)
                                   │
                                   ▼
                            WebSocket.send_json()
```

## 设计目标

1. **消除散落的 `ws.send_json()`** — 此前 19 处裸调用分布在 5 个模块中，错误处理方式不一
2. **类型安全的语义接口** — 每个事件类型有对应的命名方法，方法签名约束 payload 字段
3. **统一错误处理** — `WebSocketDisconnect` 自动标记断开，后续调用静默 no-op
4. **工厂方法统一 WS 获取** — 覆盖 `from_ws` / `from_session` / `from_session_id` / `from_context` 四种场景

## 类层次

```
WsTransport (基类)
├── TurnSender       — Agent 轮次事件
├── CallbackSender   — LangChain 回调事件
├── MemorySender     — 记忆层事件
├── ToolSender       — 工具交互事件
└── ChatSender       — 路由级事件
```

### WsTransport 基类 (`transport.py`)

```python
class WsTransport:
    def __init__(self, ws: WebSocket | None) -> None:
        self._ws = ws

    # ── 工厂方法 ──
    @classmethod
    def from_ws(cls, ws: WebSocket) -> Self
    @classmethod
    def from_session(cls, session: SessionState) -> Self | None
    @classmethod
    def from_session_id(cls, session_id: str) -> Self | None
    @classmethod
    def from_context(cls) -> Self | None

    # ── 统一发送入口 ──
    async def _send(self, event_type: str, payload: dict) -> None
```

职责：

- `_send()` 封装 `send_json()`，`WebSocketDisconnect` 时自动将 `_ws` 置为 `None`，后续调用自动跳过
- 其他异常**不吞没**，向上传播给各调用方的错误处理机制
- 工厂方法覆盖模块获取 WebSocket 引用的所有方式

### TurnSender (`turn.py`) — Agent 轮次事件

| 方法 | 推送事件 |
|------|---------|
| `context_usage(data)` | `context_usage` |
| `answer(content)` | `answer` |
| `error(code, message)` | `error` |
| `tool_error(tool_name, error)` | `tool_error` |
| `done(turn_id, context_usage)` | `done` |

取代 `api/agent/turn_sender.py` 中原有的 `WsEventSender`。通过 `TurnSender.from_context()` 获取实例——`run_agent_turn()` 执行时 `interaction.current_ws` ContextVar 已由路由层设好，随 `asyncio.create_task` 自动继承。

### CallbackSender (`callback.py`) — LangChain 回调事件

| 方法 | 推送事件 |
|------|---------|
| `thinking_start(timestamp)` | `thinking_start` |
| `token(token)` | `token` |
| `thinking_end(timestamp)` | `thinking_end` |
| `tool_start(call_id, tool_name, input)` | `tool_start` |
| `tool_end(call_id, tool_name, output, elapsed, tool_data?)` | `tool_end` + `tool_data` |
| `tool_error(call_id, tool_name, error)` | `tool_error` |

供 `WebSocketCallback` 使用，替代原有的裸 `self._ws.send_json()` 调用。通过 `CallbackSender.from_context()` 获取实例——`_build_turn_context()` 内部直接调用，无需传入 `ws`。

### MemorySender (`memory.py`) — 记忆层事件

| 方法 | 推送事件 |
|------|---------|
| `memory_start(turn_id)` | `memory_start` |
| `memory_tool_start(turn_id, tool_name, input)` | `memory_tool_start` |
| `memory_tool_end(turn_id, tool_name, output, elapsed)` | `memory_tool_end` |
| `memory_tool_error(turn_id, tool_name, error)` | `memory_tool_error` |
| `memory_done(turn_id)` | `memory_done` |

供 `long_term.py` 的 `_consumer` 和 `MemoryToolCallback` 使用。因 `_consumer` 是独立后台任务（不从 WebSocket handler 继承 ContextVar），通过 `MemorySender.from_session_id(session_id)` 获取实例，使用 `session_manager` 查找当前会话的 WebSocket 引用。

### ToolSender (`tool.py`) — 工具交互事件

| 方法 | 推送事件 |
|------|---------|
| `ask_user(tool_name, question, mode, options, interaction_id, code?)` | `ask_user` |
| `sub_session_created(sub_session_id, parent_session_id, task, name)` | `sub_session_created` |

供 `ask_user` 系列交互工具和 `call_sub_agent` 工具使用。通过 `ToolSender.from_context()` 获取实例——Agent 轮次执行时 ContextVar 由路由层设置并自动继承。

### ChatSender (`chat.py`) — 路由级事件

| 方法 | 推送事件 |
|------|---------|
| `pong()` | `pong` |
| `context_usage(data)` | `context_usage` |

供 `routes/chat.py` 使用。通过 `ChatSender.from_context()` 获取实例——`interaction.current_ws.set(ws)` 在 `ws.accept()` 后立即执行，确保整个 WebSocket handler 生命周期内均可使用。

## 工厂方法对照表

| 方法 | 参数 | 适用场景 |
|------|------|---------|
| `from_context()` | — | **首选方式**。通过 `interaction.current_ws` ContextVar 获取（路由/Agent/回调/工具层） |
| `from_session_id(session_id)` | `str` | 后台记忆层专用。`_consumer` 独立任务不继承 ContextVar，需从 session 查找 |
| `from_session(session)` | `SessionState` | 兜底备用，已有 SessionState 对象时使用 |
| `from_ws(ws)` | `WebSocket` | 兜底备用，直接注入 ws 实例（极少使用） |

## 错误处理策略

`_send()` 只捕获 `WebSocketDisconnect`（标记 `_ws = None` 后跳过后续调用），**不吞没其他异常**。各调用方各自负责异常处理：

| 调用方 | 异常处理机制 |
|--------|-------------|
| Agent 轮次 (`_execute_agent_turn`) | `try/except Exception → sender.error()` |
| LangChain 回调 (`WebSocketCallback`) | LangChain 框架捕获，触发 `on_tool_error` |
| 记忆层 (`_consumer`) | `try/except` 兜底，异常时不中断队列 |
| 工具层 | LangGraph 捕获，转为 tool_error 事件 |

## 模块文件清单

| 文件 | 职责 |
|------|------|
| `__init__.py` | 重新导出所有 Sender 类 |
| `transport.py` | `WsTransport` 基类 + 工厂方法 |
| `turn.py` | `TurnSender` — Agent 轮次事件 |
| `callback.py` | `CallbackSender` — LangChain 回调事件 |
| `memory.py` | `MemorySender` — 记忆层事件 |
| `tool.py` | `ToolSender` — 工具交互事件 |
| `chat.py` | `ChatSender` — 路由级事件 |

## 设计要点

### 按语义域拆分，而非大一统

不采用一个包含 16+ 方法的"上帝 Emitter"，而是按调用方语义拆分为 5 个独立 Sender：

- 每个 Sender 只暴露自己域的事件方法，接口最小化
- 新增事件类型只在对应的 Sender 中添加，不影响其他模块
- 前端 TS 类型 (`web/src/types/index.ts`) 中的 `ServerEvent` 联合类型与此设计天然对应

### 工厂方法解耦 WS 获取

各模块获取 WebSocket 引用的方式曾经不统一。引入 `interaction.current_ws` ContextVar 后，大多数模块统一为 `from_context()`，只有后台独立的记忆 `_consumer` 任务需要特别处理：

```python
# ★ 首选：from_context() — 路由/Agent/回调/工具层
#    ContextVar 在 ws.accept() 后设置，随 asyncio.create_task 自动继承

# 路由级
sender = ChatSender.from_context()
await sender.pong()

# Agent 轮次（run_agent_turn 内部）
sender = TurnSender.from_context()
await sender.done(turn_id, usage)

# LangChain 回调（_build_turn_context 内部）
sender = CallbackSender.from_context()
await sender.thinking_start(timestamp)

# 工具层
sender = ToolSender.from_context()
await sender.ask_user(...)

# ★ 例外：from_session_id() — 后台记忆层
#    _consumer 是服务器启动时创建的独立后台任务，不继承任何 WebSocket 的 ContextVar
sender = MemorySender.from_session_id(session_id)
await sender.memory_done(turn_id)
```

### 统一消息协议

所有事件统一遵循 `{"type": "...", "payload": {...}}` 格式，与前端 TypeScript 类型定义严格对齐。
