# 健康检查 — Health Check

```plantuml
@startuml

' ===== 样式设置 =====
skinparam classAttributeIconSize 0
skinparam backgroundColor #FEFEFE

' ===== 响应模型 =====

class ComponentHealth <<pydantic BaseModel>> {
  + status: "ok" | "error"
  + latency_ms: float | None
  + detail: str | None
}

class HealthResponse <<pydantic BaseModel>> {
  + status: "ok" | "degraded"
  + version: str
  + llm: ComponentHealth
  + memory: ComponentHealth
  + native_tools: ComponentHealth
  + mcp_tools: ComponentHealth
  + anthropic_skills_count: int
  + providers: dict[str, ComponentHealth]
  + timestamp: float
}

' ===== 检查函数（无状态模块级函数）=====

package "检查函数" {
  class check_llm {
    + {static} check_llm(app) ComponentHealth
  }
  class check_memory {
    + {static} check_memory(app) ComponentHealth
  }
  class check_native_tools {
    + {static} check_native_tools(app) ComponentHealth
  }
  class check_mcp_tools {
    + {static} check_mcp_tools(app) ComponentHealth
  }
  class check_health_providers {
    + {static} check_health_providers(app) dict[str, ComponentHealth]
  }
  class get_health_report {
    + {static} get_health_report(app) HealthResponse
  }
}

' ===== 外部依赖 =====

class httpx.AsyncClient <<httpx>> {
}

class ProviderManager <<api.providers>> {
}

class MemoryManager <<memory.memory_manager>> {
}

' ===== 关系 =====

get_health_report --> check_llm : 聚合
get_health_report --> check_memory
get_health_report --> check_native_tools
get_health_report --> check_mcp_tools
get_health_report --> check_health_providers

check_llm --> httpx.AsyncClient : HTTP POST
check_memory --> MemoryManager : 读取记忆
check_health_providers --> ProviderManager : 遍历 enabled provider

HealthResponse *-- ComponentHealth : 包含 4 个固定 + N 个 provider

@enduml
```

## 包结构

```
api/
└── health.py             # 健康检查路由 handler 和各部件检查函数
```

## 决策说明

- **LLM 健康缓存 30 秒**：避免每条健康检查请求都调用模型 API
- **聚合状态**：所有部件均为 ok → overall ok；任一 error → overall degraded
- **Provider 并行检查**：多个 enabled provider 通过 `asyncio.gather` 同时检查
