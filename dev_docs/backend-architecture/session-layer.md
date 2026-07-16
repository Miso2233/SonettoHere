# 会话管理层 — `api/session/`

## 层级定位

| 属性 | 值 |
|---|---|
| **层级编号** | 第 6 层 |
| **层级名称** | 会话管理层 |
| **依赖方向** | 不依赖上层业务模块（agent / routes / providers），仅依赖第三方库和 Python 标准库 |
| **被依赖者** | agent 编排层、routes 路由层、memory 回调层、server 启动脚本 |

```
⑤ 提供商抽象层 (providers/)
      ↑ 依赖
⑥ 会话管理层 (session/)  +  长期记忆层 (memory/)
      ↑ 依赖
⑦ 核心基础设施层 (core/)  +  数据资源层 (data/)
```

## 模块文件清单

| 文件 | 核心类型/函数 | 职责 |
|---|---|---|
| `manager.py` | `SessionState` / `SessionManager` | 会话状态管理：多会话隔离 + TTL 过期清理 |
| `const_store.py` | `save_const_session` / `delete_const_session` / `serialize_messages` | Const 固定会话 YAML 持久化 |
| `ws_registry.py` | `WebSocketRegistry` | WebSocket 连接注册表 |

## 职责描述

- **会话生命周期管理**：创建、获取、删除运行时会话，维护 `SessionState` 中的 Agent 编译图、检查点、消息计数等运行时状态
- **TTL 过期清理**：定期扫描并清理超过 TTL 阈值（默认 1800 秒）未活跃的会话
- **WebSocket 连接跟踪**：维护 session_id 到 WebSocket 连接的映射，供回调层向指定会话推送事件
- **固定会话持久化**：将会话元数据和对话消息序列化为 YAML 文件，支持保存、加载、删除

## 关键代码片段

### SessionManager 核心方法（manager.py）

```python
class SessionManager:
    def __init__(self, ttl_seconds: int = 1800):
        self._sessions: dict[str, SessionState] = {}
        self._ttl = ttl_seconds

    def create(self) -> SessionState:
        """创建新会话并注册。"""
        session_id = uuid.uuid4().hex
        session = SessionState(session_id=session_id)
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> SessionState | None:
        """获取会话，同时更新 last_active 时间戳。"""
        session = self._sessions.get(session_id)
        if session is not None:
            session.last_active = time.time()
        return session

    def get_or_create(self, session_id: str) -> SessionState:
        """获取或创建（幂等）。"""
        session = self.get(session_id)
        if session is None:
            session = SessionState(session_id=session_id)
            self._sessions[session_id] = session
        return session

    def delete(self, session_id: str) -> bool:
        """删除指定会话。"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def cleanup_expired(self) -> int:
        """清理所有过期会话，返回清理数量。"""
        now = time.time()
        expired = [
            sid for sid, s in self._sessions.items()
            if now - s.last_active > self._ttl
        ]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)
```

#### SessionState 数据结构

```python
@dataclass
class SessionState:
    session_id: str
    created_at: float
    last_active: float
    message_count: int
    _active_task: asyncio.Task | None         # 当前正在运行的 Agent 任务
    checkpointer: MemorySaver                  # LangGraph 检查点（支持 undo/重放）
    _graph: CompiledStateGraph | None          # 缓存的 Agent 编译图
    auto_approve: bool

    # Sub-agent 字段
    is_subagent: bool
    parent_session_id: str | None
    _sub_agent_task: str | None
    _pending_result: asyncio.Future | None

    # Const 固定会话字段
    is_const: bool
    const_name: str
```

### WebSocketRegistry 注册表（ws_registry.py）

```python
class WebSocketRegistry:
    """协程安全的 WebSocket 注册表。

    在 websocket_chat() accept 后 register，断开时 unregister。
    所有操作在单线程事件循环中执行，无需加锁。
    """

    def __init__(self) -> None:
        self._sessions: dict[str, WebSocket] = {}

    def register(self, session_id: str, ws: WebSocket) -> None:
        """注册 session_id → WebSocket 映射。"""
        self._sessions[session_id] = ws

    def unregister(self, session_id: str) -> None:
        """移除 session_id 的映射。"""
        self._sessions.pop(session_id, None)

    def get(self, session_id: str) -> WebSocket | None:
        """获取指定 session_id 的 WebSocket，不存在时返回 None。"""
        return self._sessions.get(session_id)
```

## 被依赖关系

| 上层模块 | 依赖内容 | 用途 |
|---|---|---|
| `api/server.py` | `SessionManager`、`WebSocketRegistry`、`const_store` 函数 | 应用启动时初始化会话管理器、注册表 |
| `api/routes/chat.py` | `SessionState` | WebSocket 聊天端点获取/创建会话 |
| `api/routes/sessions.py` | `const_store`（`flatten_content`、`save_const_session`、`delete_const_session`） | REST API：固定会话 CRUD |
| `api/agent/turn.py` | `SessionState`、`const_store`（`save_const_session`、`serialize_messages`） | Agent 轮次结束时持久化固定会话 |
| `api/agent/context_usage.py` | `SessionState` | Agent 上下文用量追踪 |
| `api/memory/callback.py` | `WebSocketRegistry` | LangChain 回调中通过注册表推送事件到前端 |
| `api/memory/narrative.py` | `SessionState`、`WebSocketRegistry` | 叙事生成时广播事件 |

## 设计要点

### 1. 线程安全

- `SessionManager` 和 `WebSocketRegistry` 均在单线程 asyncio 事件循环中运行，`dict` 操作天然协程安全，无需显式加锁
- `SessionState` 使用 `dataclass` 不可变默认值，可变字段（`_active_task`、`_pending_result`等）通过封装方法访问，避免外部直接修改内部状态

### 2. TTL 过期策略

```python
def cleanup_expired(self) -> int:
    now = time.time()
    expired = [
        sid for sid, s in self._sessions.items()
        if now - s.last_active > self._ttl
    ]
    for sid in expired:
        del self._sessions[sid]
    return len(expired)
```

- 默认 TTL：1800 秒（30 分钟），在 `SessionManager.__init__` 中配置
- 过期判定：`last_active > ttl`，每次 `get()` 调用会自动刷新 `last_active`
- 惰性清理策略：`cleanup_expired()` 不由定时器触发，而是在请求路径中按需调用（如 `list_sessions` 时附带清理）

### 3. 惰性清理

清理并非主动后台任务，而是由上层调用方在适当的时机触发：

- 会话列表查询时附带一次过期清理
- 创建新会话时检查整体会话数量上限（若需）
- 避免引入额外的后台调度复杂性

### 4. 固定会话持久化（const_store.py）

```python
def serialize_messages(raw_messages: list) -> list[dict]:
    """将 LangChain BaseMessage 对象转为可序列化的纯 dict 列表。"""
    ...

def save_const_session(session_id, const_name, metadata, messages) -> str:
    """将会话持久化为 YAML 文件。"""
    ...

def delete_const_session(session_id: str) -> bool:
    """删除 const 会话文件。"""
    ...
```

- 序列化路径：`LangChain BaseMessage` → `serialize_messages()` → `dict` → `yaml.dump()` → YAML 文件
- 存储位置：`api/data/const-sessions/{session_id}.yaml`
- 路径安全性：通过 `_validate_session_id()` 阻止路径遍历攻击

### 5. Sub-agent 机制

`SessionState` 内建对子 Agent 的支持：

- `is_subagent` / `parent_session_id`：标识子会话及其父会话
- `_pending_result`：`asyncio.Future`，用于父会话等待子会话的异步结果
- `_sub_agent_task`：存储子 Agent 任务描述，供消费

## 设计约定评估

### 违规 1：ws_registry.py 反向耦合 HTTP 传输对象

```python
from fastapi import WebSocket  # ws_registry.py 第 3 行


class WebSocketRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, WebSocket] = {}  # 存储 FastAPI WebSocket 对象
```

**问题**：会话管理层（第⑥层）内部直接存储了 `fastapi.WebSocket` 对象。`WebSocket` 是 HTTP/WebSocket 传输层（框架级）的具体类型，将传输对象存储在状态管理层中，造成了以下后果：

- 会话管理层与 FastAPI 框架耦合，难以替换或升级 Web 框架
- 单元测试时需要 mock FastAPI WebSocket 对象
- 该注册表的本质是"会话 ID → 推送通道"的抽象映射，不应暴露传输层细节

**改进建议**：

1. **接口抽象**：在 `session/` 中定义抽象的 `EventPublisher` 协议（Protocol），只暴露 `send_json()` / `send_text()` 方法，在路由层实现 FastAPI `WebSocket` 适配器
2. **泛型设计**：将 `WebSocketRegistry` 改造为泛型注册表 `Registry[SessionId, Connection]`，不关心具体连接类型
3. **最小化方案**：在 `ws_registry.py` 中对 `WebSocket` 的使用限定为只调用 `send_json()` 等方法，避免直接操作底层 ASGI 接口

### 检查通过项

| 检查项 | 结果 |
|---|---|
| `manager.py` 是否导入上层业务模块（routes / agent / providers）？ | 通过 — 仅依赖 `langgraph`、`asyncio`、标准库 |
| `const_store.py` 是否导入上层业务模块？ | 通过 — 仅依赖 `yaml`、`pathlib`、标准库 |
| `ws_registry.py` 是否导入 `api.routes` 或 `api.agent`？ | 通过 — 仅导入 `fastapi.WebSocket`（属框架级别，非业务模块） |
| 会话层是否包含 HTTP 请求处理逻辑？ | 通过 — 无 `Request` / `Response` 处理逻辑 |
| 会话层的 TTL 清理是否依赖定时器框架？ | 通过 — 纯惰性清理，无后台调度 |
