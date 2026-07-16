# 中间件层 (middleware/) — 第①层

## 层级定位

中间件层是后端分层架构中的 **第①层（最外层）**，是客户端请求进入后端系统的 **第一道关卡**。它作为 ASGI 中间件，在 FastAPI 路由分发之前拦截所有 HTTP 和 WebSocket 请求，执行横切关注点（Cross-cutting Concerns）的处理。

```
HTTP / WebSocket 客户端
       │
       ▼
┌──────────────────────┐
│ ① 中间件层 (middleware) │  ← 当前模块：认证鉴权、请求预处理
├──────────────────────┤
│ ② 路由层 (routes)     │  ← 请求分发
├──────────────────────┤
│ ③ Agent 编排层        │  ← 业务逻辑
└──────────────────────┘
```

## 模块文件清单

`api/middleware/` 目录下包含 **1 个中间件模块**（不含 `__init__.py`）：

| 文件 | 类/组件 | 类型 | 职责 |
|------|---------|------|------|
| `auth.py` | `AuthMiddleware` | ASGI 中间件 | 统一拦截 HTTP API 和 WebSocket 请求进行 Token 鉴权 |

### 模块架构

```
api/middleware/
├── __init__.py     # （空）
└── auth.py         # AuthMiddleware — ASGI 认证中间件
```

## 职责描述

中间件层的核心职责包括：

### 1. 认证鉴权

- 对所有 `/api/*` 和 `/ws/*` 路径的请求执行 Token 校验
- 鉴权失败的 HTTP 请求返回 `401 JSONResponse`
- 鉴权失败的 WebSocket 连接返回 `4001` 关闭码
- 白名单路径（如 `/api/health`）免鉴权

### 2. 请求预处理

- 从多种来源提取认证 Token（请求头、WebSocket sub-protocol）
- WebSocket 鉴权通过后，自动注入 `subprotocol` 到 `websocket.accept` 消息
- 非 API/WebSocket 路径直接放行

### 3. 不处理业务逻辑

中间件严格限定在认证鉴权范畴，不涉及任何业务逻辑处理、数据转换或服务调用。

## 实现细节

### ASGI 中间件架构

`AuthMiddleware` 实现为标准 ASGI 中间件，遵循 ASGI 规范：

```python
class AuthMiddleware:
    """ASGI 中间件 — 在请求到达路由前完成鉴权，HTTP 和 WebSocket 统一处理。"""

    def __init__(self, app):
        self.app = app  # 下一层 ASGI 应用（FastAPI 路由）

    async def __call__(self, scope, receive, send):
        # 鉴权逻辑...
        # 通过后继续传递请求到下一层
        return await self.app(scope, receive, send)
```

### 请求处理流程

```
客户端请求
    │
    ▼
AuthMiddleware.__call__(scope, receive, send)
    │
    ├── 1. 检查路径 scope["path"]
    │      ├── 非 /api/* 且非 /ws/* → 直接放行
    │      ├── /api/health → 直接放行（白名单）
    │      └── 需要鉴权
    │
    ├── 2. 提取 Token (_extract_token)
    │      ├── 通用路径: X-Sonetto-Token 请求头
    │      └── WebSocket 专用: scope.subprotocols
    │
    ├── 3. 校验 Token
    │      ├── 缺失或不匹配 → _reject()
    │      │      ├── HTTP → 401 JSONResponse
    │      │      └── WebSocket → 4001 websocket.close
    │      └── 通过
    │
    ├── 4. WebSocket subprotocol 注入
    │      ├── 拦截 websocket.accept 消息
    │      └── 自动注入 subprotocol（前端传入的 Token）
    │
    └── 5. 放行到下一层
           return await self.app(scope, receive, send)
```

### Token 校验机制

Token 的来源有两个路径：

| 来源 | 适用场景 | 提取方式 |
|------|---------|----------|
| `X-Sonetto-Token` 请求头 | HTTP API + WebSocket | `scope["headers"]` 中解析 `b"x-sonetto-token"` |
| `Sec-WebSocket-Protocol` (subprotocols) | WebSocket 浏览器 | `scope["subprotocols"][0]`（ASGI server 自动解析） |

Token 优先级：`X-Sonetto-Token` 请求头优先，WebSocket subprotocols 作为备选。校验方式为 **精确字符串匹配**，与 `app.state.auth_token` 对比。

### 白名单机制

当前白名单仅包含健康检查路径 `/api/health`，用于 Kubernetes 或 Docker 的健康探针免鉴权访问。

## 设计要点

### 无状态

`AuthMiddleware` 是无状态的 —— 它不维护任何会话状态、缓存或连接池。每次请求独立鉴权，不存在会话污染风险。

### 可组合

ASGI 中间件遵循 `(scope, receive, send) → coroutine` 的通用接口，可以与其他 ASGI 中间件（如 CORS、GZip、TrustedHost）自由组合，唯一的依赖是下一层 `self.app`。

### 不处理业务逻辑

中间件的职责严格限定在认证鉴权范围：

- 不做请求/响应体解析
- 不调用下层服务（session manager、provider manager 等）
- 不修改业务数据
- 不记录审计日志（日志应在 application 层面处理）

### 安全性考虑

- 未经鉴权的 WebSocket 连接在握手阶段即被关闭（4001），不占用后续资源
- Token 比较使用 `!=` 而非 `==` 以避免类型相关的意外行为（两者在 Python 中行为一致，但使用 `!=` 更明确地表达了预期结果）
- `subprotocols` 注入避免前端重复协商协议，但对 `scope` 的修改仅限于 `send` 回调，不修改原始 `scope`

## 关键代码片段

### AuthMiddleware.__call__ 核心逻辑 (`auth.py`)

```python
class AuthMiddleware:
    """ASGI 中间件 — 在请求到达路由前完成鉴权，HTTP 和 WebSocket 统一处理。"""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")

        # 仅保护 API 和 WebSocket 路径
        if not path.startswith("/api/") and not path.startswith("/ws/"):
            return await self.app(scope, receive, send)

        # 白名单：健康检查
        if path == "/api/health":
            return await self.app(scope, receive, send)

        # 提取并校验 Token
        token = self._extract_token(scope)
        app = scope.get("app")
        expected = app.state.auth_token if app is not None else None

        if not expected or token != expected:
            return await self._reject(scope, receive, send)

        # WebSocket 鉴权通过后：拦截 handler 的 websocket.accept 消息，
        # 自动注入 subprotocol（前端通过 new WebSocket(url, [token]) 请求的协议），
        # 业务 handler 无需感知 sub-protocol 协商细节。
        if scope["type"] == "websocket":
            protocols = scope.get("subprotocols", [])
            if protocols:
                original_send = send

                async def _accept_with_subprotocol(message):
                    if message.get("type") == "websocket.accept" and not message.get("subprotocol"):
                        message = {**message, "subprotocol": protocols[0]}
                    await original_send(message)

                return await self.app(scope, receive, _accept_with_subprotocol)

        return await self.app(scope, receive, send)
```

### Token 提取逻辑

```python
def _extract_token(self, scope) -> str:
    """从请求头提取 Token。

    HTTP / WebSocket 通用路径: X-Sonetto-Token 自定义头
    WebSocket 专用路径: scope.subprotocols（由 ASGI server/uvicorn 从
    Sec-WebSocket-Protocol 握手头部解析，前端通过 new WebSocket(url, [token])
    传入）。优先使用 subprotocols 字段，比手动解析 raw header 更可靠。
    """
    headers = dict(scope.get("headers", []))

    # 通用：X-Sonetto-Token 自定义头
    token_bytes = headers.get(b"x-sonetto-token", b"")
    if token_bytes:
        return token_bytes.decode()

    # WebSocket 专用：从 ASGI scope 的 subprotocols 字段提取
    # ASGI server 在握手时自动解析 Sec-WebSocket-Protocol 头部，
    # 存入 scope["subprotocols"] = [token]
    if scope["type"] == "websocket":
        protocols = scope.get("subprotocols", [])
        if protocols:
            return protocols[0]

    return ""
```

### 拒绝响应逻辑

```python
async def _reject(self, scope, receive, send):
    """根据 scope 类型返回 HTTP 401 或 WebSocket 4001 关闭。"""
    if scope["type"] == "websocket":
        await send({"type": "websocket.close", "code": 4001})
    else:
        response = JSONResponse(
            {"detail": "Unauthorized — X-Sonetto-Token 缺失或不匹配"},
            status_code=401,
        )
        await response(scope, receive, send)
```

## 设计约定评估

| 原则 | 遵守情况 | 说明 |
|------|---------|------|
| 无状态 | 通过 | 中间件不维护任何状态，每次请求独立鉴权 |
| 可组合 | 通过 | 标准 ASGI 中间件接口，可与其他中间件链式组合 |
| 不处理业务逻辑 | 通过 | 仅做 Token 比对和路径放行 |
| 从 app.state 读取配置 | 通过 | Token 通过 `app.state.auth_token` 获取，由启动时注入 |
| 统一处理 HTTP 和 WebSocket | 通过 | 单一中间件覆盖两种协议，4001 和 401 分别对应 |

暂无发现分层违规。中间件层严格遵循了关注点分离的原则，职责清晰，边界明确。
