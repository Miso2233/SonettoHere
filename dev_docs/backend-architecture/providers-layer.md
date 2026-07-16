# 提供商抽象层 (providers/)

## 层级定位

**第⑤层 — LLM 提供商抽象层**。位于 Agent 编排层（第③层）之下，会话管理层与记忆层（第⑥层）之上。为上层 Agent 和 REST 接口提供统一的 LLM 提供商接入能力，屏蔽不同 API 厂商的差异。

```
③ Agent 编排层 ─────────────────────► ⑤ providers/  (create_llm / check_health)
⑥ session/ + memory/ ───────────────► ⑤ providers/  (获取默认 LLM)
```

## 模块文件清单

| 文件 | 职责 |
|------|------|
| `__init__.py` | Provider 抽象基类、ProviderConfig 与 HealthStatus 数据类定义 |
| `manager.py` | ProviderManager — 按 id 索引，管理所有已注册 Provider 实例 |
| `store.py` | ProviderConfigStore — `providers.yaml` 文件存储的 CRUD |
| `openai_provider.py` | OpenAIProvider — OpenAI 兼容 API 的通用实现 |
| `enrich.py` | 模型元数据并发检测入口 + `register()` 注册机制 |
| `vision.py` | 模型视觉能力检测：`test_model_vision` / `detect_vision_if_available` |
| `model_context_windows.py` | 从 OpenRouter API 拉取模型上下文窗口数据 |
| `capabilities/` | 预留子包，待扩展 |

## 职责描述

### 1. LLM 提供商统一抽象

通过 `Provider` 抽象基类定义所有提供商必须实现的接口，上层代码面向抽象编程，不依赖具体实现。

```python
# api/providers/__init__.py

class Provider(ABC):
    """所有 LLM 提供商必须实现的接口。"""

    def __init__(self, config: ProviderConfig):
        self.config = config

    @property
    def provider_name(self) -> str:
        return self.config.id

    @property
    def default_model(self) -> str:
        if self.config.default_model and self.config.default_model in self.config.models:
            return self.config.default_model
        return self.config.models[0] if self.config.models else ""

    @property
    def available_models(self) -> list[str]:
        return self.config.models

    @abstractmethod
    def create_llm(self, model: str, **kwargs) -> BaseChatModel:
        """根据指定模型名创建 LangChain ChatModel 实例。"""
        ...

    @abstractmethod
    async def check_health(self) -> HealthStatus:
        """验证提供商 API 连接是否正常。"""
        ...
```

### 2. 多模型支持与动态发现

`ProviderConfig` 的数据模型设计支持一个 Provider 下挂多个模型，`ProviderManager` 负责按 id 索引并提供查询接口。

### 3. 连接测试与健康检测

每轮健康检测通过 `AsyncOpenAI.client.models.list()` 执行真实 API 调用，返回状态（ok/error）和延迟（ms）。

```python
# api/providers/openai_provider.py

class OpenAIProvider(Provider):
    def create_llm(self, model: str, **kwargs) -> BaseChatModel:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model,
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            **kwargs,
        )

    async def check_health(self) -> HealthStatus:
        import time
        from openai import AsyncOpenAI
        start = time.monotonic()
        try:
            client = AsyncOpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url,
            )
            await client.models.list()
            elapsed = (time.monotonic() - start) * 1000
            return HealthStatus(status="ok", latency_ms=round(elapsed, 1))
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            return HealthStatus(status="error", latency_ms=round(elapsed, 1), detail=str(exc))
```

### 4. 模型能力检测

视觉能力和上下文窗口的检测以 **enrichment 注册机制** 实现：

```python
# api/providers/enrich.py

_registry: list[Callable[[ProviderConfig], object]] = []

def register(func: Callable[[ProviderConfig], object]) -> None:
    """注册一个 enrichment 函数，入参为 ProviderConfig，原地修改。"""
    _registry.append(func)

# 注册内置 enrichment
register(detect_vision_if_available)
register(fill_missing_context_windows)

async def enrich_provider_config(config: ProviderConfig) -> None:
    """并发执行所有已注册的 enrichment 函数。"""
    await asyncio.gather(*(f(config) for f in _registry))
```

视觉检测逻辑：向模型发送一张含 "Sonetto" 文字的测试图片，要求模型读出文字，若响应包含 "Sonetto" 则判定为有视觉能力。

上下文窗口检测逻辑：从 OpenRouter /api/v1/models 拉取全量数据，按精确匹配 → 后缀匹配 → 子串匹配的优先级补充缺失值。OpenRouter 是唯一数据源，无硬编码兜底。

## 设计要点

### 策略模式

`Provider` 抽象基类定义了策略接口，`OpenAIProvider` 是策略的具体实现。`ProviderManager._build_provider` 充当策略工厂，根据 `config.provider_type` 实例化对应的策略。

```python
@staticmethod
def _build_provider(config: ProviderConfig) -> Provider:
    if config.provider_type == "openai":
        from api.providers.openai_provider import OpenAIProvider
        return OpenAIProvider(config)
    msg = f"Unknown provider type: {config.provider_type}"
    raise ValueError(msg)
```

### 开放封闭原则

- **扩展（开放）**：新增提供商只需实现 `Provider` 抽象类，并在 `_build_provider` 工厂中添加一条分支。
- **封闭（封闭）**：上层代码（Agent 编排、REST 路由）通过 `ProviderManager.create_llm()` 或 `ProviderManager.get_default_llm()` 获取 LLM，无需感知具体 Provider 类型。
- **enrichment 机制**：新增元数据检测能力只需 `@register` 装饰一个 `(ProviderConfig) -> object` 函数，核心代码无需修改。

### 动态检测

每次保存/更新提供商配置时，`enrich_provider_config` 自动并发执行：
- 视觉能力检测（每个模型独立测试）
- 上下文窗口补全（从 OpenRouter 拉取）

所有检测结果原地填充到 `ProviderConfig` 的 `model_vision` 和 `model_context_windows` 字段。

## 扩展性评估

### 添加一个新的 Provider 类型

**修改文件数：2~3 个**

| 步骤 | 文件 | 操作 |
|------|------|------|
| 1 | `api/providers/my_provider.py` | **新增**，实现 `class MyProvider(Provider)`，实现 `create_llm` 和 `check_health` |
| 2 | `api/providers/manager.py` | **修改** `_build_provider` 工厂，添加 `elif config.provider_type == "my_type":` 分支 |
| 3 | （可选）`api/providers/enrich.py` | 若需自定义 enrichment，注册新函数 |

**完整流程**：
1. 创建新文件实现 `Provider` 接口
2. 在 `_build_provider` 工厂注册映射
3. 配置 `providers.yaml` 中设置 `provider_type: "my_type"`
4. 重启或调用 reload 即可生效

### 添加一个新的 enrichment 能力

**修改文件数：1 个**（仅需在任意文件中定义并用 `register()` 装饰，无需修改核心代码）

### 设计约定评估

**发现的分层违规**：

1. **工厂硬编码**：`ProviderManager._build_provider` 中的 provider_type → 实现类的映射是硬编码的。理想情况下应通过注册表机制（如 `register_provider_type("openai", OpenAIProvider)`）实现，使新增提供商时无需修改 `manager.py`。当前设计违背了开放封闭原则的"封闭"要求。

2. **Vision 检测直接实例化**：`vision.py` 中的 `detect_vision_capabilities` 硬编码 `OpenAIProvider(config)`，绕过工厂方法。若新增非 OpenAI 的 Provider 类型，视觉检测逻辑需要更新来适配。

**改进建议**：
- 在 `Provider` 基类中添加类方法或注册机制，使 `_build_provider` 变为动态查找。
- `vision.py` 应从 `ProviderManager` 获取 Provider 实例，而非直接 `import OpenAIProvider`。
