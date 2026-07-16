# SonettoHere 后端架构

## 架构总览

SonettoHere 后端采用**分层架构**（Layer Architecture），共有 **7 个层级**，从上到下依次为：

```
┌──────────────────────────────────────┐
│          HTTP / WebSocket             │  客户端请求入口
├──────────────────────────────────────┤
│  ① 中间件层 (middleware/)             │  横切关注点：认证、鉴权
├──────────────────────────────────────┤
│  ② 路由层 (routes/)                   │  请求分发：REST API + WebSocket
├──────────────────────────────────────┤
│  ③ Agent 编排层 (agent/)              │  对话编排：LLM 调用、工具执行、轮次管理
├──────────────────────────────────────┤
│  ④ 回调层 (callbacks/)                │  事件驱动：LLM 事件 → WebSocket 推送
├──────────────────────────────────────┤
│  ⑤ 提供商抽象层 (providers/)           │  LLM 抽象：多模型支持、动态发现
├──────────────────────────────────────┤
│  ⑥ 长期记忆层 (memory/) +             │  持久化：记忆管理、文件存储
│     会话管理层 (session/)              │  状态管理：会话隔离、生命周期
├──────────────────────────────────────┤
│  ⑦ 核心基础设施层 (core/) +            │  基础设施：认证 Token、健康检查
│     数据资源层 (data/)                 │  静态资源：系统新闻、测试数据
└──────────────────────────────────────┘
```

## 依赖方向

依赖关系是**单向向下的**，上层依赖下层，下层不依赖上层：

```
routes/ → middleware/ → agent/ → providers/ → session/ + memory/ + core/ + data/
                   ↘ callbacks/
```

## 模块清单

| 模块目录 | 层级 | 职责 |
|---|---|---|
| [middleware/](middleware-layer.md) | ① | ASGI 中间件，认证与鉴权 |
| [routes/](routes-layer.md) | ② | FastAPI 路由器，REST + WebSocket 端点 |
| [agent/](agent-layer.md) | ③ | Agent 对话编排，LLM 轮次管理 |
| [callbacks/](callbacks-layer.md) | ④ | LangChain 回调，WebSocket 事件推送 |
| [providers/](providers-layer.md) | ⑤ | 多 LLM 提供商抽象与动态发现 |
| [memory/](memory-layer.md) | ⑥ | 长期记忆 CRUD 与 LLM 叙事 |
| [session/](session-layer.md) | ⑥ | 会话状态管理、WebSocket 引用 |
| [core/](core-layer.md) | ⑦ | 基础设施：Auth、Health、Dependencies |
| [data/](data-layer.md) | ⑦ | 静态数据资源 |

## 请求处理流程

### REST API 流程

```
客户端 → AuthMiddleware → Router → Handler(路由函数) → Provider/Manager → 响应
```

### WebSocket 聊天流程

```
WebSocket 连接 → AuthMiddleware → Route(chat.py) → 事件派发
  → chat 事件: Agent(turn.py) → Provider(LLM) → callbacks(WebSocket推送)
  → user_response 事件: Agent → TimeTravel
  → memory 操作: MemoryManager → YAML 文件
```

## 关键技术栈

- **框架**: FastAPI（Python 异步 Web 框架）
- **LLM**: 多提供商抽象（OpenAI 兼容 API）
- **序列化**: Pydantic v2（数据模型与验证）
- **异步**: asyncio + async generators（流式响应）
- **持久化**: YAML 文件存储（记忆、会话、配置）
- **回调**: LangChain BaseCallbackHandler（事件推送）
