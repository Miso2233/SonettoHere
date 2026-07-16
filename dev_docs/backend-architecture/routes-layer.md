# 路由层 (routes/) — 第②层

## 层级定位

路由层是后端分层架构中的 **第②层**，位于中间件层之下、Agent 编排层之上。它负责 **HTTP 请求分发与 WebSocket 事件派发**，本身不包含业务逻辑，仅作为将客户端请求路由到下层服务的薄胶合层。

```
HTTP / WebSocket 客户端
       │
       ▼
┌──────────────────────┐
│ ① 中间件层 (middleware) │  ← 认证鉴权
├──────────────────────┤
│ ② 路由层 (routes)     │  ← 请求分发（当前模块）
├──────────────────────┤
│ ③ Agent 编排层        │  ← 业务逻辑
└──────────────────────┘
```

## 模块文件清单

`api/routes/` 目录下共 **15 个路由模块**（不含 `__init__.py`），按功能分类如下：

| 文件 | 职责 | 端点类型 |
|------|------|----------|
| `chat.py` | WebSocket 主端点：连接管理、事件派发（ping, chat, user_response, cancel, update_auto_approve） | WebSocket |
| `sessions.py` | 会话 CRUD、Const 固定会话、撤回 (undo)、上下文用量查询、标题生成 | REST |
| `providers.py` | LLM 提供商 CRUD、连接测试、模型发现 | REST |
| `memory.py` | 长期记忆叙事获取、记忆分组列表、随机 moment | REST |
| `persona.py` | 人设文件 (SOUL.md / USER.md) 读写 | REST |
| `env_vars.py` | 工具环境变量管理 (.env 文件读写) | REST |
| `files.py` | 本地文件选择对话框 (tkinter) | REST |
| `images.py` | 本地图片文件提供（含安全策略校验） | REST |
| `mcp.py` | MCP 服务器配置查看与热加载 | REST |
| `news.py` | 系统更新动态列表 | REST |
| `balance.py` | DeepSeek 余额查询 | REST |
| `path_whitelist.py` | 路径白名单 CRUD 与路径安全检查 | REST |
| `restart.py` | 后端进程重启 | REST |
| `skills.py` | Anthropic Skills / Macros / 内置工具列表 | REST |
| `sonetto_blocker.py` | 拒止锚 (SonettoBlocker) 管理（创建/删除标记文件） | REST |

### 各文件详细说明

#### `chat.py` — WebSocket 聊天端点

WebSocket 连接的生命周期管理核心文件。定义了 `websocket_chat` 端点 (`/ws/chat/{session_id}`)，职责包括：

1. **连接初始化**：接受 WebSocket、获取/创建会话、注册 WebSocket 到注册表
2. **推送初始上下文用量**：估算当前会话的 token 占用并推送给前端
3. **断线重连恢复**：若会话有未完成的 sub-agent 任务则自动恢复执行
4. **消息主循环**：通过字典派发 (`_HANDLERS`) 将消息分发给对应的事件处理器

支持的事件类型：

| 事件 | 处理器 | 功能 |
|------|--------|------|
| `ping` | `_handle_ping` | 心跳保活，回复 `pong` |
| `chat` | `_handle_chat` | 创建 Agent 轮次，启动 `run_agent_turn` 异步任务 |
| `user_response` | `_handle_user_response` | 处理用户对 Agent 交互请求的响应 |
| `cancel` | `_handle_cancel` | 取消正在运行的 Agent 任务 |
| `update_auto_approve` | `_handle_update_auto_approve` | 更新自动批准设置 |

#### `sessions.py` — 会话管理

提供完整的会话 CRUD 操作及高级功能：

| 端点 | 方法 | 功能 |
|------|------|------|
| `/sessions` | POST | 创建新会话 |
| `/sessions` | GET | 列出所有会话 |
| `/sessions/{session_id}` | GET | 获取单个会话详情 |
| `/sessions/{session_id}/messages` | GET | 获取会话消息历史 |
| `/sessions/{session_id}` | DELETE | 删除会话（const 会话同时清理磁盘） |
| `/sessions/{session_id}/undo` | POST | 撤回最近 N 轮对话 |
| `/sessions/{session_id}/context-usage` | GET | 查询上下文用量 |
| `/sessions/{session_id}/const` | POST | 将会话固定为 const 持久化 |
| `/sessions/{session_id}/const` | DELETE | 取消固定，删除 const 磁盘文件 |
| `/sessions/{session_id}/generate-title` | POST | 使用 LLM 生成会话标题 |

#### `providers.py` — LLM 提供商管理

完整的提供商配置生命周期管理：

| 端点 | 方法 | 功能 |
|------|------|------|
| `/providers` | GET | 列出所有提供商 |
| `/providers/{provider_id}` | GET | 获取单个提供商配置 |
| `/providers` | POST | 新增提供商（含模型元数据自动填充） |
| `/providers/{provider_id}` | PUT | 更新提供商配置 |
| `/providers/{provider_id}` | DELETE | 删除提供商 |
| `/providers/test` | POST | 测试任意凭据的连接 |
| `/providers/{provider_id}/test` | POST | 测试已保存提供商的连接 |
| `/providers/discover-models` | POST | 根据凭据拉取模型列表 |
| `/providers/{provider_id}/discover-models` | POST | 拉取并更新已保存提供商的模型列表 |

新增/更新提供商后会调用 `_refresh_app_llm` 刷新应用全局 LLM 实例，并同步长期记忆 (LTM) 消费者的启停。

#### `memory.py` — 长期记忆

| 端点 | 方法 | 功能 |
|------|------|------|
| `/narrative` | GET | 获取当前叙事文本 |
| `/memories` | GET | 获取按主题分组的记忆列表 |
| `/moment` | GET | 随机获取一条记忆 moment（含描述历史） |

#### `persona.py` — 人设文件

| 端点 | 方法 | 功能 |
|------|------|------|
| `/persona` | GET | 读取 SOUL.md 或 USER.md 内容 |
| `/persona` | PUT | 写入 SOUL.md 或 USER.md 内容 |

#### `env_vars.py` — 环境变量管理

| 端点 | 方法 | 功能 |
|------|------|------|
| `/env-vars` | GET | 列出所有已知环境变量（值脱敏显示） |
| `/env-vars` | PUT | 更新单个环境变量并持久化到 .env |
| `/env-vars/batch` | PUT | 批量更新多个环境变量 |

更新后通过 `importlib.reload` 刷新运行时配置。

#### `files.py` — 文件选择对话框

| 端点 | 方法 | 功能 |
|------|------|------|
| `/select-file` | GET | 打开系统原生文件选择对话框（tkinter），返回所选路径 |

仅在本地开发环境可用。

#### `images.py` — 图片文件服务

| 端点 | 方法 | 功能 |
|------|------|------|
| `/images/serve` | GET | 根据绝对路径返回图片文件（含安全策略校验） |

安全策略包括：限制常见图片扩展名、SonettoBlocker 拒止锚检查、路径白名单检查。

#### `mcp.py` — MCP 服务器管理

| 端点 | 方法 | 功能 |
|------|------|------|
| `/mcp/servers` | GET | 返回所有已配置的 MCP 服务器信息 |
| `/mcp/reload` | POST | 热加载 MCP 配置：重新解析 YAML、重建连接、替换工具列表 |

热加载失败时保留旧工具列表不变。

#### `news.py` — 系统更新动态

| 端点 | 方法 | 功能 |
|------|------|------|
| `/news` | GET | 返回所有更新动态（按日期降序排列） |

#### `balance.py` — 余额查询

| 端点 | 方法 | 功能 |
|------|------|------|
| `/deepseek-balance` | GET | 查询 DeepSeek 账户余额 |

通过扫描已配置的提供商列表，自动查找 base_url 包含 `deepseek.com` 的提供商并使用其 API Key。

#### `path_whitelist.py` — 路径白名单

| 端点 | 方法 | 功能 |
|------|------|------|
| `/path-whitelist` | GET | 列出所有白名单条目 |
| `/path-whitelist` | POST | 添加白名单条目 |
| `/path-whitelist/{index}` | PUT | 更新指定索引的白名单条目 |
| `/path-whitelist/{index}` | DELETE | 删除指定索引的白名单条目 |
| `/check-path-blocked` | GET | 检查路径是否被拒止锚或白名单阻挡 |

#### `restart.py` — 后端重启

| 端点 | 方法 | 功能 |
|------|------|------|
| `/restart` | POST | 启动新后端进程后优雅退出当前进程 |

通过 `subprocess.Popen` 启动新进程，然后 `sys.exit(0)` 触发 FastAPI lifespan shutdown。

#### `skills.py` — 技能与工具列表

| 端点 | 方法 | 功能 |
|------|------|------|
| `/skills` | GET | 扫描 `anthropic_skills/` 目录，返回所有 SKILL.md 的结构化列表 |
| `/macros` | GET | 扫描 `macros/` 目录，返回所有 MACRO.md 的结构化列表 |
| `/tools` | GET | 返回所有已加载的内置工具（native_tools + mcp_tools） |

#### `sonetto_blocker.py` — 拒止锚管理

| 端点 | 方法 | 功能 |
|------|------|------|
| `/sonetto-blocker` | GET | 列出所有拒止锚条目 |
| `/sonetto-blocker` | POST | 添加拒止锚（在目标目录创建标记文件） |
| `/sonetto-blocker/{index}` | DELETE | 删除拒止锚（移除标记文件和持久化记录） |

## 职责描述

路由层的核心职责限定为以下三点：

### 1. 解析 HTTP/WebSocket 请求参数

- 从 FastAPI 的路径参数、Query 参数、Request body 中提取客户端传入的数据
- 使用 Pydantic 模型 (`BaseModel` 子类) 进行请求体验证与类型转换
- WebSocket 消息通过 `json.loads` 解析为字典后按 `type` 字段派发

### 2. 调用下层服务

- 通过 `request.app.state` 获取生命周期托管全局单例（如 `tool_manager`、`ltm`），或直接导入模块级单例（如 `session_manager`、`get_manager()`）
- 调用下层服务的公开方法执行业务逻辑
- 路由函数本身不包含业务逻辑实现，仅作为编排入口

### 3. 序列化响应并返回

- 将下层服务的返回值转换为 Pydantic response 模型或字典
- 处理异常情况（如资源不存在返回 404、冲突返回 409、服务不可用返回 503）
- WebSocket 消息通过 `ws.send_json()` 推送 JSON 格式响应

## 数据流

### REST 请求流程

```
客户端 HTTP 请求
       │
       ▼
AuthMiddleware (①) ─── Token 校验 ─── 失败 → 401 JSONResponse
       │ 通过
       ▼
FastAPI Router ─── 路径匹配 → 路由处理函数
       │
       ▼
路由函数:
  1. 获取下层服务（app.state 或模块级单例）
  2. 调用下层服务方法
  3. 返回 Pydantic 模型 / 字典
       │
       ▼
FastAPI 自动序列化为 JSON 响应 → 客户端
```

### WebSocket 消息流程

```
客户端 WebSocket 连接 → /ws/chat/{session_id}
       │
       ▼
AuthMiddleware ─── Token 校验 ─── 失败 → 4001 close
       │ 通过
       ▼
chat.py: websocket_chat()
  1. ws.accept() — 接受连接
  2. 获取/创建 SessionState
  3. 设置 session.ws（供后台记忆推送事件）
  4. 推送初始 context_usage
  5. 断线重连时恢复 sub-agent
       │
       ▼
消息主循环 (while True):
  ws.receive_text() → json.loads(msg)
       │
       ├── type="ping"    → _handle_ping    → 回复 pong
       ├── type="chat"    → _handle_chat    → 创建 asyncio.Task → run_agent_turn
       ├── type="user_response" → _handle_user_response → interaction.resolve()
       ├── type="cancel"  → _handle_cancel  → agent_task.cancel()
       └── type="update_auto_approve" → _handle_update_auto_approve → 更新设置
       │
       ▼ (chat 事件)
Agent 编排层 — run_agent_turn()
       │
       ├── Provider (LLM 调用)
       ├── Callbacks (WebSocket 事件推送)
       └── Session (消息持久化)
```

## 设计约定

### 分层边界原则

| 原则 | 说明 | 遵守情况 |
|------|------|----------|
| 路由不包含业务逻辑 | 路由函数应仅为薄胶合层，业务逻辑委托给下层服务 | 基本遵守 |
| 路由不直接操作 LLM | LLM 调用应通过 agent 层或 provider 层进行 | 基本遵守（`generate-title` 通过 `ProviderManager` 获取 LLM） |
| 路由不直接操作文件系统 | 文件读写应封装在专门的 service/store 层 | **部分违反**（见下文） |
| 路由不直接操作数据库 | 数据库操作应通过 session/memory 层 | 无不涉及数据库 |

### 已识别的分层违规

在审阅代码时发现以下 **分层违规** 情况，路由层直接操作了文件系统或系统调用：

#### 违规 1: 路由直接读写文件

以下路由模块直接使用 `Path.read_text()` / `Path.write_text()` 或 YAML 文件 API 操作持久化存储：

- `persona.py` — 直接读写 `config/personas/SOUL.md` 和 `USER.md`
- `env_vars.py` — 直接通过 `dotenv.set_key()` 写入 `.env` 文件
- `path_whitelist.py` — 直接读写 `config/path_whitelist.yaml`
- `sonetto_blocker.py` — 直接读写 `config/sonetto_blocker.yaml` 并创建/删除文件系统标记文件
- `news.py` — 直接读取 `api/data/news.yaml`

**改进建议**：将这些文件操作抽取为独立的 service 模块（如 `services/persona_service.py`、`services/env_service.py`），路由层仅调用 service 接口。

#### 违规 2: 路由直接启动子进程

- `restart.py` — 直接在路由函数中调用 `subprocess.Popen` 和 `sys.exit(0)`
- `files.py` — 直接在路由函数中调用 `tkinter.filedialog`（该操作本质上是 GUI 系统调用）

**改进建议**：将进程管理逻辑封装在 `core/` 层的服务中，路由层仅暴露端点。

#### 违规 3: 路由直接使用第三方 HTTP 客户端

- `balance.py` — 直接在路由函数中使用 `httpx.AsyncClient` 调用 DeepSeek API

**改进建议**：将 HTTP 请求封装到服务层（如 `services/balance_service.py`），路由层调用服务接口。

#### 违规 4: 路由处理复杂业务逻辑

- `sessions.py` — `generate_title` 函数中包含大量 prompt 拼接逻辑、LLM 调用异常处理、响应解析逻辑

**改进建议**：将标题生成逻辑抽取为独立的 service 函数，路由层仅调用 `generate_session_title(session)`。

## 关键代码片段

### WebSocket 事件派发核心逻辑 (`chat.py`)

以下是 WebSocket 消息主循环和基于字典的事件派发机制：

```python
# 事件处理器注册表
_HANDLERS: dict[str, Handler] = {}

def ws_event_handler(event_type: str):
    """装饰器：将 handler 函数注册到 _HANDLERS 字典。"""
    def decorator(func):
        _HANDLERS[event_type] = func
        return func
    return decorator

# ── 消息主循环（字典派发） ─────────────────────────────
# （位于 websocket_chat 函数内）
try:
    while True:
        raw = await ws.receive_text()
        msg = json.loads(raw)

        handler = _HANDLERS.get(msg.get("type", ""))
        if handler is not None:
            agent_task = await handler(
                ws, session_id, session, agent_task, msg, app_state
            )

except WebSocketDisconnect:
    pass  # 客户端断开是正常行为
finally:
    session.ws = None
    if agent_task is not None and not agent_task.done():
        agent_task.cancel()
    session.clear_active_task()
    interaction.clear_session_settings(session_id)
```

关键设计特点：

- **装饰器注册模式**：通过 `@ws_event_handler("type")` 将处理函数注册到 `_HANDLERS` 字典，新增事件类型只需添加新的 handler 函数
- **统一签名**：所有 handler 接收相同参数签名 `(ws, session_id, session, agent_task, msg, app_state)`，返回更新后的 `agent_task`
- **Agent 任务单例**：对话轮次通过 `asyncio.create_task` 启动，由 `session.set_active_task()` 跟踪，保证同时只有一个 Agent 任务在运行

### 典型 REST 处理函数 (`sessions.py`)

以创建会话端点为例，展示 REST 路由的标准模式：

```python
@router.post("/sessions")
async def create_session(request: Request):
    from api.session.manager import session_manager
    session = session_manager.create()
    return {"session_id": session.session_id, "created_at": session.created_at}
```

以获取会话端点为例，展示含错误处理的模式：

```python
@router.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request):
    from api.session.manager import session_manager
    session = session_manager.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": session.session_id,
        "message_count": session.message_count,
        "created_at": session.created_at,
        "has_active_agent": session.has_active_task(),
        "is_const": session.is_const,
        "const_name": session.const_name,
    }
```

模式总结：

1. 获取全局服务实例（`app.state` 或模块级单例）
2. 调用服务方法（`sm.get()`, `sm.create()` 等）
3. 对 None 结果返回 404 HTTPException
4. 返回字典或 Pydantic 模型作为响应
