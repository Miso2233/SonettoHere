# 会话管理 — Session Manager

```plantuml
@startuml

' ===== 样式设置 =====
skinparam classAttributeIconSize 0
skinparam backgroundColor #FEFEFE

' ===== 数据类 =====

class SessionState <<dataclass>> {
  + session_id: str
  + created_at: float
  + last_active: float
  + message_count: int
  + checkpointer: MemorySaver
  + is_subagent: bool
  + parent_session_id: str | None
  _active_task: asyncio.Task | None
  _sub_agent_task: str | None
  _pending_result: asyncio.Future | None
}

' ===== 管理器 =====

class SessionManager {
  - _sessions: dict[str, SessionState]
  - _ttl: int
  + create() SessionState
  + create_sub_session(task, parent_session_id) SessionState
  + get(session_id) SessionState | None
  + get_or_create(session_id) SessionState
  + delete(session_id) bool
  + list_sessions() list[dict]
  + cleanup_expired() int
}

' ===== 外部依赖 =====

class MemorySaver <<langgraph.checkpoint>> {
}

class asyncio.Task <<asyncio>> {
}

class asyncio.Future <<asyncio>> {
}

' ===== 关系 =====

SessionManager o-- SessionState : manages
SessionState *-- MemorySaver : checkpointer
SessionState o-- asyncio.Task : _active_task
SessionState o-- asyncio.Future : _pending_result

SessionManager --> SessionState : create / get 返回

@enduml
```

## 包结构

```
api/
└── session_manager.py    # SessionState, SessionManager
```

## 数据流

```
SessionManager
  ├─ create() → 新会话（无 checkpointer 历史）
  ├─ get_or_create(id) → 恢复已有/创建新会话
  ├─ create_sub_session() → Sub-agent 会话（带 parent + pending_result）
  ├─ list_sessions() → 排序后的活跃会话列表
  └─ cleanup_expired() → TTL（默认 30 分钟）过期清理
```
