# 会话管理 — Session Manager

```plantuml
@startuml

' ===== 样式设置 =====
skinparam classAttributeIconSize 0
skinparam backgroundColor #FEFEFE

' ===== 子数据类 =====

class SessionMeta <<dataclass>> {
  + session_id: str
  + created_at: float
  + last_active: float
  + message_count: int
}

class AgentRuntime <<dataclass>> {
  + checkpointer: MemorySaver
  _active_task: asyncio.Task | None
  _graph: CompiledStateGraph | None
}

class SubAgentData <<dataclass>> {
  + is_subagent: bool
  _sub_agent_task: str | None
  _pending_result: asyncio.Future | None
}

class ConstSession <<dataclass>> {
  + is_const: bool
  + const_name: str
}

' ===== 组合层 =====

class SessionState {
  + meta: SessionMeta
  + runtime: AgentRuntime
  + sub_agent: SubAgentData
  + const: ConstSession
  + ws: WebSocket | None
}

note top of SessionState
  组合层：通过属性/方法
  转发子数据类的字段与方法，
  保持外部接口不变
end note

' ===== 管理器 =====

class SessionManager {
  - _sessions: dict[str, SessionState]
  - _ttl: int
  + create() SessionState
  + create_sub_session(task) SessionState
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

SessionState *-- SessionMeta : meta
SessionState *-- AgentRuntime : runtime
SessionState *-- SubAgentData : sub_agent
SessionState *-- ConstSession : const

AgentRuntime *-- MemorySaver : checkpointer
AgentRuntime o-- asyncio.Task : _active_task
SubAgentData o-- asyncio.Future : _pending_result

SessionManager --> SessionState : create / get 返回

@enduml
```

## 包结构

```
api/
└── session/
    └── manager.py        # SessionMeta, AgentRuntime, SubAgentData, ConstSession,
                          # SessionState, SessionManager, session_manager
    └── const_store.py    # 固定会话 YAML 持久化
```

## 数据流

```
SessionManager
  ├─ create() → 新会话（无 checkpointer 历史）
  ├─ get_or_create(id) → 恢复已有/创建新会话
  ├─ create_sub_session(task) → Sub-agent 会话（带 pending Future）
  ├─ list_sessions() → 排序后的活跃会话列表
  └─ cleanup_expired() → TTL（默认 30 分钟）过期清理
```
