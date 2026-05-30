# REST 路由 — 业务端点

```plantuml
@startuml

' ===== 样式设置 =====
skinparam classAttributeIconSize 0
skinparam backgroundColor #FEFEFE

' ===== 会话路由 =====

class SessionsRouter <<FastAPI APIRouter>> {
  + POST /api/sessions
  + GET /api/sessions
  + GET /api/sessions/{id}
  + GET /api/sessions/{id}/messages
  + GET /api/sessions/{id}/context-usage
  + DELETE /api/sessions/{id}
}

' ===== 记忆路由 =====

class MemoryRouter <<FastAPI APIRouter>> {
  + GET /api/narrative
  + GET /api/moment
}

' ===== 文件路由 =====

class FileRouter <<FastAPI APIRouter>> {
  + GET /api/select-file?type=file|folder
  + GET /api/file?path=
}

' ===== 余额路由 =====

class BalanceRouter <<FastAPI APIRouter>> {
  + GET /api/deepseek-balance
}

' ===== 更新动态路由 =====

class NewsRouter <<FastAPI APIRouter>> {
  + GET /api/news
}

class NewsEntry <<pydantic BaseModel>> {
  + id: str
  + en_title: str | None
  + title: str
  + description: str
  + type: str
  + date: str
  + tags: list[str]
  + version: str
  + pr_number: int | None
}

class ListNewsResponse <<pydantic BaseModel>> {
  + news: list[NewsEntry]
}

' ===== 外部依赖 =====

class SessionManager <<api.session_manager>> {
}

class LongTermMemoryInterface <<memory.narrative>> {
}

class MemorySaver <<langgraph.checkpoint>> {
}

class MemoryManager <<memory.memory_manager>> {
}

' ===== 关系 =====

SessionsRouter --> SessionManager : 委托全部操作
SessionsRouter --> MemorySaver : 读取消息历史

MemoryRouter --> LongTermMemoryInterface : 读取叙事
MemoryRouter --> MemoryManager : 读取记忆条目

FileRouter --> FileResponse : 返回文件

NewsRouter --> NewsEntry : 加载 & 返回
ListNewsResponse *-- NewsEntry : 列表

@enduml
```

## 包结构

```
api/routes/
├── __init__.py
├── sessions.py    # 会话 CRUD
├── memory.py      # 长期记忆叙事
├── files.py       # 本地文件服务
├── balance.py     # DeepSeek 余额查询
├── news.py        # 系统更新动态
└── providers.py   # Provider CRUD（见 Bay Project UML）
```

## 路由挂载（server.py）

| Router          | Prefix   | 说明                     |
|-----------------|----------|--------------------------|
| sessions        | `/api`   | 会话 CRUD + 消息查询     |
| memory          | `/api`   | 长期记忆叙事读取         |
| files           | `/api`   | 本地文件选择与提供       |
| balance         | `/api`   | DeepSeek 余额查询        |
| chat            | 无       | WebSocket `/ws/chat/{id}` |
| providers       | `/api`   | Provider CRUD            |
| news            | `/api`   | 系统更新动态             |
