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
| `manager.py` | `SessionMeta` / `AgentRuntime` / `SubAgentData` / `ConstSession` / `SessionState` / `SessionManager` / `session_manager` | 会话状态管理：多会话隔离 + TTL 过期清理（模块级单例）。`SessionState` 组合四个子数据类，通过属性/方法转发保持对外接口不变 |
| `const_store.py` | `save_const_session` / `delete_const_session` / `serialize_messages` | Const 固定会话 YAML 持久化 |

### 外部依赖

| 外部模块 | 用途 |
|---|---|
| `api/memory/short_term.py` | 全局 MemorySaver 单例 — `SessionState` 通过 `short_term.get_checkpointer()` 获取短期记忆存储，`cleanup_expired()` / `delete()` 通过 `short_term.delete_thread(sid)` 释放记忆内存 |

## 职责描述

- **会话生命周期管理**：创建、获取、删除运行时会话，维护 `SessionState` 中的 Agent 编译图、检查点、消息计数等运行时状态
- **TTL 过期清理**：定期扫描并清理超过 TTL 阈值（默认 1800 秒）未活跃的会话
- **WebSocket 引用管理**：`SessionState.ws` 字段存储当前会话的 WebSocket 连接，供回调层向指定会话推送事件
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
            _delete_memory_thread(session_id)  # 释放短期记忆
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
            _delete_memory_thread(sid)  # 释放短期记忆
        return len(expired)
```

#### SessionState 数据结构

SessionState 由四个子数据类组合而成：

```python
@dataclass
class SessionMeta:
    """会话基础元信息"""
    session_id: str
    created_at: float
    last_active: float
    message_count: int

@dataclass
class AgentRuntime:
    """Agent 运行时状态"""
    _active_task: asyncio.Task | None    # 当前正在运行的 Agent 任务
    checkpointer: MemorySaver | None      # 可选的自定义 checkpointer（默认 None → 回退到全局单例）
    _graph: CompiledStateGraph | None     # 缓存的 Agent 编译图

@dataclass
class SubAgentData:
    """Sub-agent 会话状态"""
    is_subagent: bool
    _sub_agent_task: str | None
    _pending_result: asyncio.Future | None

@dataclass
class ConstSession:
    """固定会话标记"""
    is_const: bool
    const_name: str

class SessionState:
    """组合层 — 转发子数据类的字段与方法"""
    meta: SessionMeta
    runtime: AgentRuntime
    sub_agent: SubAgentData
    const: ConstSession
    ws: WebSocket | None                 # 当前 WebSocket 连接，供后台推送事件

    async def get_messages(self) -> list[BaseMessage]:
        """获取当前会话的对话消息列表（从全局 checkpointer 按 thread_id 查询）"""
```

- **无 `checkpointer` 属性**：`SessionState` 不再暴露整个 MemorySaver。图编译所需的 checkpointer 通过 `short_term.get_checkpointer()` 直接获取；消息读取通过 `session.get_messages()` 封装，内部自动用 `session_id` 作 `thread_id` 查询全局单例

### SessionState.ws — WebSocket 引用

`ws_registry.py` 已删除。WebSocket 引用不再通过独立注册表管理，而是直接存入 `SessionState.ws` 字段：

- **route 端**：`websocket_chat()` accept 后设置 `session.ws = ws`，断开时设 `session.ws = None`
- **memory 端**：`LongTermMemory._consumer()` 和 `MemoryToolCallback._send()` 通过 `session_manager.get(sid).ws` 直接获取
- **生命周期绑定**：ws 引用跟随 SessionState，无需独立的 register/unregister 注册表

## 被依赖关系

| 上层模块 | 依赖内容 | 用途 |
|---|---|---|
| `api/server.py` | `SessionState`、`session_manager`、`const_store` 函数 | 应用启动时 `_load_const_sessions` 重建固定会话 |
| `api/routes/chat.py` | `SessionState`、`session_manager` | WebSocket 聊天端点获取/创建会话，设置 `session.ws` |
| `api/routes/sessions.py` | `session_manager`、`const_store`（`flatten_content`、`save_const_session`、`delete_const_session`） | REST API：会话 CRUD + 固定会话 CRUD |
| `api/agent/turn.py` | `SessionState`、`const_store`（`save_const_session`、`serialize_messages`）、`api.memory.short_term.get_checkpointer` | Agent 轮次编排：`session.get_messages()` 读取消息，`get_checkpointer()` 构建图 |
| `api/agent/context_usage.py` | `SessionState` | Agent 上下文用量追踪（通过 `session.get_messages()`） |
| `api/memory/callback.py` | `session_manager`（通过 `session_manager.get(sid).ws`） | LangChain 回调中获取 ws 引用推送事件到前端 |
| `api/memory/long_term.py` | `SessionState`（`session.get_messages()`）、`session_manager` | 叙事生成：提取会话消息并广播事件 |
| `tools/sub_agent/tool_call_sub_agent.py` | `session_manager` | 创建子会话 |

## 设计要点

### 1. 线程安全

- `SessionManager` 在单线程 asyncio 事件循环中运行，`dict` 操作天然协程安全，无需显式加锁
- `SessionState` 通过组合多个子数据类（`SessionMeta`、`AgentRuntime`、`SubAgentData`、`ConstSession`）组织会话状态。私有字段（`_active_task`、`_pending_result` 等）封装在子数据类中通过方法访问，避免外部直接修改内部状态

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
        _delete_memory_thread(sid)  # 同步清理全局 MemorySaver 中该 thread_id 的检查点
    return len(expired)
```

- 默认 TTL：1800 秒（30 分钟），在 `SessionManager.__init__` 中配置
- 过期判定：`last_active > ttl`，每次 `get()` 调用会自动刷新 `last_active`
- 惰性清理策略：`cleanup_expired()` 不由定时器触发，而是在请求路径中按需调用（如 `list_sessions` 时附带清理）
- **记忆回收**：会话过期时同步调用 `short_term.delete_thread(sid)`，从全局 MemorySaver 单例中删除该 thread_id 的所有检查点，防止内存泄漏

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

`SubAgentData` 内建对子 Agent 的支持（通过 `SessionState.sub_agent` 访问）：

- `is_subagent`：标识子会话
- `_pending_result`：`asyncio.Future`，用于父会话等待子会话的异步结果
- `_sub_agent_task`：存储子 Agent 任务描述，供消费

### 6. 模块级单例

`SessionManager` 不在 `app.state` 上挂载，而是以模块级实例 `session_manager` 的形式暴露：

```python
# api/session/manager.py — 文件末尾
session_manager = SessionManager()
```

所有消费者直接 `from api.session.manager import session_manager` 使用，无需经过 `app.state`。这与 `ProviderManager`（`get_manager()`）、`default_llm`（`get_default_llm()`）采用相同的模块级单例模式。

**不通过 `app.state` 的原因**：`SessionManager` 无生命周期方法（无 `close()`/`stop()`/`start()`），是一个纯内存 dict 封装。无需应用生命周期管理。

## 设计约定评估

### 检查通过项

| 检查项 | 结果 |
|---|---|
| `manager.py` 是否导入上层业务模块（routes / agent / providers）？ | 通过 — 仅依赖 `langgraph`、`fastapi`、`asyncio`、`langchain_core.messages`、同级 `api.memory.short_term`、标准库 |
| `const_store.py` 是否导入上层业务模块？ | 通过 — 仅依赖 `yaml`、`pathlib`、标准库 |
| `SessionState` 中的 `ws` 字段类型为 `WebSocket` 是否合理？ | 通过 — `WebSocket` 仅作为引用存储（不在此层创建或管理连接生命周期），且依赖方向为框架级（非业务模块） |
| 会话层是否包含 HTTP 请求处理逻辑？ | 通过 — 无 `Request` / `Response` 处理逻辑 |
| 会话层的 TTL 清理是否依赖定时器框架？ | 通过 — 纯惰性清理，无后台调度 |
