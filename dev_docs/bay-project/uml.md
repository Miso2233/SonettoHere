# Project Bay 湾区计划 — 后端 UML 类图

```plantuml
@startuml

' ===== 样式设置 =====
skinparam classAttributeIconSize 0
skinparam backgroundColor #FEFEFE

' ===== 类型定义 =====

class ProviderConfig <<dataclass>> {
  + id: str
  + provider_type: str
  + label: str
  + api_key: str
  + base_url: str
  + models: list[str]
  + enabled: bool
  + to_dict() dict
}

class HealthStatus <<dataclass>> {
  + status: Literal["ok", "error"]
  + latency_ms: float | None
  + detail: str | None
}

' ===== 抽象基类 =====

abstract class Provider {
  # config: ProviderConfig
  + {abstract} create_llm(model, **kwargs) BaseChatModel
  + {abstract} check_health() HealthStatus
  + {static} provider_name: str
  + {static} default_model: str
  + {static} available_models: list[str]
}

' ===== 具体实现 =====

class OpenAIProvider {
  + create_llm(model, **kwargs) BaseChatModel
  + check_health() HealthStatus
}

class OpenRouterProvider <<Phase 5 预留>> {
}

' ===== YAML 存储 =====

class ProviderConfigStore {
  - path: Path
  + load_all() list[ProviderConfig]
  + get(provider_id) ProviderConfig | None
  + save(config) None
  + delete(provider_id) bool
  + is_empty: bool
  + migrate_from_env() ProviderConfig | None
  - _write_all(configs) None
}

' ===== 管理器 =====

class ProviderManager {
  - _store: ProviderConfigStore
  - _providers: dict[str, Provider]
  + load_all() None
  + reload() None
  + get(provider_id) Provider
  + iter_enabled() Iterator[Provider]
  + has(provider_id) bool
  + count: int
  - _build_provider(config) Provider
}

' ===== 路由 =====

class ProvidersRouter <<FastAPI APIRouter>> {
  + GET /api/providers
  + GET /api/providers/{id}
  + POST /api/providers
  + PUT /api/providers/{id}
  + DELETE /api/providers/{id}
  + POST /api/providers/{id}/test
  + POST /api/providers/discover-models
  + POST /api/providers/{id}/discover-models
}

' ===== 外部依赖 =====

class BaseChatModel <<langchain_core>> {
}

class ChatOpenAI <<langchain_openai>> {
}

class AsyncOpenAI <<openai SDK>> {
}

class YamlFile <<providers.yaml>> {
}

' ===== 关系 =====

' --- 继承 ---
Provider <|-- OpenAIProvider
Provider <|-- OpenRouterProvider

' --- 持有 ---
Provider o-- ProviderConfig : holds

' --- 管理器关系（全部通过 ProviderConfigStore 访问文件）---
ProviderManager o-- ProviderConfigStore : delegates persistence
ProviderManager o-- Provider : manages
ProviderManager --> Provider : creates via _build_provider()

' --- 存储关系（ProviderConfigStore 是唯一文件访问者）---
ProviderConfigStore --> ProviderConfig : returns
ProviderConfigStore --> YamlFile : reads/writes

' --- 外部依赖 ---
OpenAIProvider --> BaseChatModel : create_llm() returns
OpenAIProvider --> AsyncOpenAI : check_health() calls
OpenAIProvider --> ChatOpenAI : wraps in create_llm()

' --- 路由关系（仅依赖 ProviderManager，不直接操作文件）---
ProvidersRouter --> ProviderManager : all CRUD delegates

@enduml
```

## 包结构

```
api/providers/
├── __init__.py          # Provider, ProviderConfig, HealthStatus
├── store.py             # ProviderConfigStore（YAML 读写）
├── manager.py           # ProviderManager（管理 Provider 生命周期）
└── openai_provider.py   # OpenAIProvider（ChatOpenAI 封装）

api/routes/
└── providers.py         # CRUD + 连接测试 + 模型发现路由

api/server.py            # 应用工厂：初始化 ProviderManager
api/health.py            # 健康检查：聚合多 provider 状态
```

## 核心数据流

```
providers.yaml
     ↓ (读取)
ProviderConfigStore.load_all()
     ↓ (list[ProviderConfig])
ProviderManager.load_all()
     ↓ (过滤 enabled → 创建实例)
ProviderManager._providers: dict[str, Provider]
     ↓
Chat 路由 / Health 路由 → ProviderManager.get(id) → Provider.create_llm(model)
```
