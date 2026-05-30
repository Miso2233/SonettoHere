# 应用核心 — 应用工厂与依赖

```plantuml
@startuml

' ===== 样式设置 =====
skinparam classAttributeIconSize 0
skinparam backgroundColor #FEFEFE

' ===== 应用状态容器 =====

class AppState <<FastAPI app.state>> {
  + llm: BaseChatModel
  + system_prompt: str
  + native_tools: list
  + mcp_tools: list
  + tools: list
  + session_manager: SessionManager
  + provider_manager: ProviderManager
  + ltm: LongTermMemoryInterface
}

' ===== 依赖工厂 =====

class Dependencies {
  + {static} get_llm(provider_manager) BaseChatModel
  + {static} get_system_prompt() str
  + {static} get_tools() list
}

' ===== 外部依赖 =====

class FastAPI <<FastAPI>> {
  + lifespan
  + add_middleware()
  + include_router()
  + mount()
}

class BaseChatModel <<langchain_core>> {
}

class LongTermMemoryInterface <<memory.narrative>> {
  + start_listening(llm)
  + stop_listening()
  + send_history(messages)
  + get_narrative()
}

class ProviderManager <<api.providers>> {
}

class SessionManager <<api.session_manager>> {
}

class CORSMiddleware <<starlette>> {
}

class StaticFiles <<starlette>> {
}

class FileResponse <<starlette>> {
}

' ===== 关系 =====

Dependencies --> BaseChatModel : get_llm() 返回
Dependencies --> ProviderManager : 优先从此创建

AppState *-- BaseChatModel : llm
AppState *-- SessionManager : session_manager
AppState *-- ProviderManager : provider_manager
AppState *-- LongTermMemoryInterface : ltm

FastAPI --> CORSMiddleware : 添加
FastAPI --> AppState : .state
FastAPI --> StaticFiles : 挂载 /assets
FastAPI --> FileResponse : SPA fallback

@enduml
```

## 包结构

```
api/
├── server.py             # create_app() — FastAPI 应用工厂 + lifespan
├── dependencies.py       # get_llm, get_system_prompt, get_tools
```

## 生命周期流程

```
FastAPI lifespan (startup)
  ├─ ProviderConfigStore → ProviderManager.load_all()
  ├─ get_llm(provider_manager) → BaseChatModel
  ├─ get_system_prompt() → str
  ├─ get_tools() → list[BaseTool]
  ├─ SessionManager()
  ├─ LongTermMemoryInterface → start_listening()
  ├─ init_mcp_tools() → mcp_tools
  └─ tools = native_tools + mcp_tools

FastAPI lifespan (shutdown)
  ├─ close_mcp()
  └─ ltm.stop_listening()
```
