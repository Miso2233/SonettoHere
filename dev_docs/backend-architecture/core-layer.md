# 核心基础设施层 — `api/core/`

## 层级定位

| 属性 | 值 |
|---|---|
| **层级编号** | 第 7 层（最底层） |
| **层级名称** | 核心基础设施层 |
| **依赖方向** | 不依赖其他业务模块，仅依赖第三方库和 Python 标准库 |
| **被依赖者** | server 启动脚本、main 入口、中间件层、路由层 |

```
⑥ 长期记忆层 + 会话管理层 (memory/ + session/)
      ↑ 依赖
⑦ 核心基础设施层 (core/)
      ↑ 依赖
   第三方库 / 标准库
```

## 模块文件清单

| 文件 | 核心类型/函数 | 职责 |
|---|---|---|
| `auth.py` | `load_or_create_token()` / `rotate_token()` | Token 认证：从 YAML 加载或生成新 Token，支持安全轮换 |
| `dependencies.py` | `get_system_prompt()` / `get_tools()` | 共享资源惰性单例：系统提示词 + 工具集的全局单例 |
| `health.py` | `ComponentHealth` / `HealthResponse` / `get_health_report()` | 四部件健康自检：LLM / 记忆 / 原生工具 / MCP 工具 |

### auth.py — Token 认证

```python
AUTH_TOKEN_PATH = Path(...) / "config" / "auth_token.yaml"


def load_or_create_token() -> str:
    """从 auth_token.yaml 加载 Token，不存在则生成并持久化。"""
    ...


def rotate_token() -> str:
    """轮换 Token，覆盖写入文件并返回新值。"""
    ...
```

### dependencies.py — 惰性单例

```python
_system_prompt: str | None = None
_tools: list | None = None


def get_system_prompt() -> str:
    global _system_prompt
    if _system_prompt is None:
        _system_prompt = build_system_prompt()
    return _system_prompt


def get_tools() -> list:
    global _tools
    if _tools is None:
        _tools = get_all_tools()
    return _tools
```

### health.py — 健康自检

```python
class ComponentHealth(BaseModel):
    status: Literal["ok", "error"]
    latency_ms: float | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    llm: ComponentHealth          # LLM 连通性
    memory: ComponentHealth       # 记忆文件 + 后台消费者
    native_tools: ComponentHealth # 内置工具集
    mcp_tools: ComponentHealth    # MCP 工具集
    anthropic_skills_count: int
    providers: dict[str, ComponentHealth]
    timestamp: float
```

四个健康检查函数各自独立，互不依赖：

- **check_llm** — 遍历 ProviderManager 中所有 enabled provider，逐个调用 `provider.check_health()`，第一个成功的即返回 `ok`，全部失败则返回 `error`
- **check_memory** — 检查记忆 YAML 文件是否存在，并验证后台消费者（ltm）是否在运行
- **check_native_tools** — 从 `app.state.native_tools` 读取工具列表，验证其可访问性
- **check_mcp_tools** — 从 `app.state.mcp_tools` 读取 MCP 工具列表，空列表视为 `ok`（未配置 MCP 服务器即正常状态）

最终 `get_health_report()` 聚合四部件结果：

```python
async def get_health_report(app: FastAPI) -> HealthResponse:
    llm = await check_llm(app)
    memory = await check_memory(app)
    native_tools = await check_native_tools(app)
    mcp_tools = await check_mcp_tools(app)
    providers = await check_health_providers(app)

    all_checks = [llm, memory, native_tools, mcp_tools] + list(providers.values())
    overall = "ok" if all(c.status == "ok" for c in all_checks) else "degraded"

    return HealthResponse(status=overall, version=__version__, ...)
```

## Token 轮换逻辑（auth.py）

```python
def rotate_token() -> str:
    """轮换 Token，覆盖写入文件并返回新值。"""
    token = secrets.token_urlsafe(32)
    AUTH_TOKEN_PATH.write_text(
        yaml.dump({"token": token}, encoding="utf-8").decode("utf-8"),
        encoding="utf-8",
    )
    return token
```

使用 `secrets.token_urlsafe(32)` 生成 256 位随机 Token，直接覆写 YAML 文件。无状态设计 —— 不保留内存副本，每次调用从文件读取或生成新的 Token。

## 职责描述

- **无状态基础设施**：所有函数均为纯函数或惰性初始化，不持有运行时可变状态
- **跨模块共享**：系统提示词和工具集通过惰性单例在全局范围内共享，避免重复构建
- **健康自检**：提供 LLM、记忆、工具四个维度的健康检查，供监控和路由层使用
- **认证凭证管理**：Token 的生成、持久化、轮换，供中间件层认证使用

## 被依赖关系

| 上层模块 | 依赖内容 |
|---|---|
| `api/server.py`（应用启动） | `load_or_create_token`、`get_system_prompt`、`get_tools`、`get_health_report` |
| `main.py`（CLI 入口） | `rotate_token` |
| `api/middleware/`（中间件层） | 间接通过 `server.py` 注入 Token 验证逻辑 |
| `api/routes/`（路由层） | 间接通过 `server.py` 注册健康检查端点（`/api/health`） |

## 设计要点

### 1. 单例模式（dependencies.py）

```python
_system_prompt: str | None = None
_tools: list | None = None
```

通过模块级全局变量 + 双重惰性初始化实现单例。`get_system_prompt()` 和 `get_tools()` 仅在首次调用时构建一次，后续直接返回缓存结果。该模式：

- 避免了 FastAPI 启动时的冷启动开销
- 线程安全（CPython GIL 保护全局变量赋值）
- 不支持动态重新加载（如需更新需重启服务）

### 2. 无状态设计（auth.py / health.py）

- `auth.py` 不保留 Token 内存副本，每次认证由中间件从文件加载
- `health.py` 的每个检查函数都是独立的，不共享内部状态
- `HealthResponse` 是值对象（Pydantic BaseModel），一次性构造后不可变

### 3. 健康检查的策略

每项检查独立 try/except，某项失败不影响其他项的结果收集。最终 status 只有当**全部**部件正常才为 `ok`，任一部件异常则整体为 `degraded`。

## 设计约定评估

### 发现：health.py 存在向上依赖违规

`api/core/health.py` 中存在对上层模块的引用：

```python
from api.memory.manager import MemoryManager        # 依赖 memory/（第⑥层）
from api.memory.narrative import MEMORY_PATH         # 依赖 memory/（第⑥层）
```

**问题**：第⑦层（core）不应依赖第⑥层（memory）。根据"下层不依赖上层"的约定，`health.py` 中对 `MemoryManager` 的调用构成了自底向上的反向依赖。

**影响**：该依赖使 `core/` 无法在脱离 `memory/` 模块的环境下独立测试或复用。

**改进建议**：

1. **接口抽象**：在 `core/` 内定义健康检查接口（Protocol），将 `check_memory` 的具体实现注入（如通过 FastAPI `app.state` 传递），而不是直接 import memory 模块
2. **挪动位置**：将 `check_memory` 函数移至 `memory/` 模块，由 health 端点通过依赖注入聚合结果
3. **当前权宜方案**：若短期内不改，可通过 `app.state.memory_manager` 注入 MemoryManager 实例，避免硬导入
