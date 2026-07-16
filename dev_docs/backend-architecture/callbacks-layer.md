# 回调层 (api/callbacks/)

## 层级定位

**第④层 — 回调层**，事件驱动机制。

位于 Agent 编排层之下、提供商抽象层之上。该层不参与业务逻辑或对话编排，仅做一件事：**监听 LangChain 事件，转换为结构化 JSON，推送前端 WebSocket**。

回调层是连接"后端 LLM 执行"与"前端实时渲染"的桥梁，承担着低延迟、高吞吐的事件转发任务。

## 模块文件清单

| 文件 | 职责 | 主要类型/函数 |
|---|---|---|
| `websocket_callback.py` | LangChain → WebSocket JSON 事件推送 | `WebSocketCallback(BaseCallbackHandler)` |
| `tool_extractors.py` | 工具输出数据提取器，注册/调度模式 | `register()`, `register_prefix()`, `_dispatch()` |

### 核心数据结构

**`WebSocketCallback`** — LangChain 回调处理器，继承 `BaseCallbackHandler`：

| 属性 | 类型 | 说明 |
|---|---|---|
| `_ws` | `WebSocket` | 底层 WebSocket 连接 |
| `_thinking_started` | `bool` | LLM 思考阶段标志，用于配对 `thinking_start` / `thinking_end` |
| `_tool_start_time` | `dict[str, float]` | run_id → 开始时间戳，用于计算工具执行耗时 |
| `_tool_names` | `dict[str, str]` | run_id → 工具名称 |
| `_tool_inputs` | `dict[str, str]` | run_id → 工具输入原文 |

**提取器签名**（`tool_extractors.py`）：

```python
Handler = Callable[[str, dict[str, Any], str | None], dict[str, Any] | None]
# (tool_name, parsed_json, tool_input) → 前端数据 dict 或 None
```

## 职责描述

### 1. 监听 LangChain LLM/工具调用事件

通过继承 `BaseCallbackHandler` 并覆写事件方法，接入 LangChain 的执行链路：

| 事件 | 触发时机 | 推送事件类型 |
|---|---|---|
| `on_llm_start` | LLM 开始生成 | `thinking_start` |
| `on_llm_new_token` | LLM 生成新的 token | `token` |
| `on_llm_end` | LLM 生成完成 | `thinking_end` |
| `on_tool_start` | 工具开始执行 | `tool_start` |
| `on_tool_end` | 工具执行完成 | `tool_end` + 可选 `tool_error` |
| `on_tool_error` | 工具执行异常 | `tool_error` |

### 2. 实时推送到前端 WebSocket

所有事件统一包装为 `{"type": ..., "payload": ...}` 格式，通过 `ws.send_json()` 推送。

### 3. 工具输出结构化提取

`tool_extractors.py` 实现 Registry + Dispatch 模式，将工具输出 JSON 转换为前端气泡组件所需的结构化数据。

## 关键代码片段

### 事件处理器（`websocket_callback.py`）

**LLM 事件** — 流式 token 的核心路径：

```python
class WebSocketCallback(BaseCallbackHandler):
    def __init__(self, ws: WebSocket):
        super().__init__()
        self._ws = ws
        self._thinking_started = False
        self._tool_start_time: dict[str, float] = {}
        self._tool_names: dict[str, str] = {}
        self._tool_inputs: dict[str, str] = {}

    async def on_llm_start(self, serialized, prompts, **kwargs):
        self._thinking_started = True
        await self._ws.send_json({
            "type": "thinking_start",
            "payload": {"timestamp": time.time()},
        })

    async def on_llm_new_token(self, token: str, **kwargs):
        await self._ws.send_json({
            "type": "token",
            "payload": {"token": token},
        })

    async def on_llm_end(self, response, **kwargs):
        if self._thinking_started:
            self._thinking_started = False
            await self._ws.send_json({
                "type": "thinking_end",
                "payload": {"timestamp": time.time()},
            })
```

**工具事件** — 工具调用全生命周期跟踪：

```python
    async def on_tool_start(self, serialized, input_str, **kwargs):
        tool_name = serialized.get("name", "unknown")
        run_id = str(kwargs.get("run_id", ""))
        self._tool_start_time[run_id] = time.time()
        self._tool_names[run_id] = tool_name
        self._tool_inputs[run_id] = input_str

        await self._ws.send_json({
            "type": "tool_start",
            "payload": {
                "call_id": run_id,
                "tool_name": tool_name,
                "input": input_str[:500],
            },
        })

    async def on_tool_end(self, output, **kwargs):
        run_id = str(kwargs.get("run_id", ""))
        elapsed = time.time() - self._tool_start_time.pop(run_id, time.time())
        tool_name = self._tool_names.pop(run_id, "unknown")
        tool_input = self._tool_inputs.pop(run_id, None)

        out_str = _extract_content(output)

        # 检测 format_error 响应 → 路由到 tool_error
        try:
            parsed = json.loads(out_str)
            if isinstance(parsed, dict) and parsed.get("success") is False:
                # 推送 tool_error 事件
                return
        except (json.JSONDecodeError, TypeError):
            pass

        # 提取工具专属结构化数据
        tool_data = self._extract_tool_data(tool_name, output, tool_input)

        await self._ws.send_json({
            "type": "tool_end",
            "payload": {
                "call_id": run_id,
                "tool_name": tool_name,
                "output": out_str[:300],
                "elapsed": round(elapsed, 2),
                "tool_data": tool_data,
            },
        })
```

### 注册/调度机制（`tool_extractors.py`）

**Registry 模式** — 装饰器注册 + 运行时调度：

```python
# Registry
_REGISTRY: dict[str, Handler] = {}
_PREFIX_REGISTRY: list[tuple[str, Handler]] = []

def register(tool_name: str) -> Callable[[Handler], Handler]:
    """精确匹配注册装饰器。"""
    def decorator(fn: Handler) -> Handler:
        _REGISTRY[tool_name] = fn
        return fn
    return decorator

def register_prefix(prefix: str) -> Callable[[Handler], Handler]:
    """前缀匹配注册装饰器（如 todo_*）。"""
    def decorator(fn: Handler) -> Handler:
        _PREFIX_REGISTRY.append((prefix, fn))
        return fn
    return decorator

# Dispatch
def _dispatch(tool_name, parsed, tool_input=None):
    handler = _REGISTRY.get(tool_name)
    if handler:
        return handler(tool_name, parsed, tool_input)

    for prefix, handler in _PREFIX_REGISTRY:
        if tool_name.startswith(prefix):
            return handler(tool_name, parsed, tool_input)

    return None
```

**典型提取器示例** — Todo 系列工具使用精确匹配和前缀匹配组合：

```python
@register("todo_list")
def _extract_todo_list(_tool_name, parsed, _tool_input=None):
    """返回 tool_type=task_list, total, tasks。"""
    data = _get_data(parsed)
    if data is None:
        return None
    return {"tool_type": "task_list", "total": data.get("total"), "tasks": data.get("tasks", [])}

@register_prefix("todo_")
def _extract_todo_generic(tool_name, parsed, _tool_input=None):
    """前缀匹配兜底：todo_create, todo_update, todo_delete 等均由此处理。"""
    data = _get_data(parsed)
    if data is None:
        return None
    return {"tool_type": "single_task", ...}
```

## 事件流程

```
LangChain 执行链路               WebSocketCallback               前端
─────────────────               ────────────────               ────

LLM 开始生成
    │
    ├── on_llm_start()  ──────→  {"type":"thinking_start"}  ──→ 显示思考状态
    │
    ├── on_llm_new_token()  ──→  {"type":"token"}            ──→ 追加流式文本
    │         ... (多次)
    │
    ├── on_llm_end()      ──────→  {"type":"thinking_end"}   ──→ 隐藏思考状态
    │
工具开始执行
    │
    ├── on_tool_start()   ──────→  {"type":"tool_start"}     ──→ 显示工具气泡(loading)
    │
    ├── on_tool_end()     ──────→  {"type":"tool_end"}       ──→ 更新工具气泡(完成)
    │                             附 tool_data(结构化数据)
    │
    └── on_tool_error()   ──────→  {"type":"tool_error"}     ──→ 工具气泡(错误)

*tool_end 中检测到 format_error (success=false) 时也路由到 tool_error
```

## 设计要点

### 松耦合

- `WebSocketCallback` 通过 `BaseCallbackHandler` 接口与 LangChain 集成，不依赖任何 Agent 编排细节
- 提取器系统通过装饰器注册，新增工具只需添加新装饰器函数，无需修改调度逻辑
- `WsEventSender`（位于 agent 层）和 `WebSocketCallback`（位于 callbacks 层）共享同一 `WebSocket` 实例，但职责互补：前者发送编排层事件（`context_usage`、`answer`、`done`），后者发送 LangChain 事件（`token`、`tool_start/end`）

### 可扩展

- 工具提取器支持精确匹配（`register("exact_name")`）和前缀匹配（`register_prefix("prefix_")`）两种模式
- 目前内置 20+ 个提取器，覆盖 Todo、文件系统、天气、地图、塔罗、搜索、记忆等工具域
- 新工具只需添加装饰函数，无需修改其他代码

### 不阻塞主流程

- 所有 `ws.send_json()` 为异步调用，`await` 不会阻塞 LangChain 事件循环
- `_dispatch()` 提取器是纯同步函数，执行极快，不涉及 IO
- 工具输出摘取前 300 字符以防大数据量阻塞 WebSocket

## 分层边界

回调层严格遵守 **"只做事件转换和推送，不处理业务逻辑"** 的边界原则：

| 职责范围内 | 职责范围外 |
|---|---|
| LangChain 事件 → JSON 序列化 | LLM 调用参数构造 |
| 工具输出 → 结构化解构 | 工具执行结果验证 |
| 错误检测 → 事件路由（tool_error） | 对话状态管理 |
| 耗时统计 | 消息持久化 |
| 字符串截断（防大数据推送） | 用户鉴权 |

## 设计约定评估

### 分层纯净度

**约定**：回调层应仅依赖 LangChain SDK 和 FastAPI WebSocket，不依赖后端的业务模块（session、memory、tools 等）。

**评估结果**：**合规**。`websocket_callback.py` 的导入链清晰：
- `fastapi.WebSocket` — 框架基础
- `langchain_core.callbacks.BaseCallbackHandler` — LangChain SDK
- `langchain_core.outputs.LLMResult` — LangChain 类型
- `.tool_extractors` — 同层模块引用

无任何对 `api/session/`、`api/memory/`、`tools/`、`agent/` 的导入。

### 职责单一

**约定**：一个文件只做一件事。

**评估结果**：**合规**。
- `websocket_callback.py` 只做事件推送
- `tool_extractors.py` 只做结构化数据提取

`tool_extractors.py` 包含大量提取函数（20+ 个），但这些都属于"同一个职责"——工具输出到前端气泡数据的映射。通过装饰器注册机制保持扩展点统一。

### 事件完整性

**约定**：LLM 事件必须有始有终（成对推送）。

**评估结果**：`thinking_start` / `thinking_end` 通过 `_thinking_started` 标志保证配对，**合规**。
工具事件（`tool_start` / `tool_end`）通过 `run_id` 关联，`_tool_start_time` / `_tool_names` / `_tool_inputs` 三个字典均在 `on_tool_end` 中 `pop` 清理，**合规**。

### 错误路由正确性

**约定**：工具执行失败应走 `tool_error` 事件，而非 `tool_end`。

**评估结果**：**合规**。`on_tool_end` 中有专门的检测逻辑：
```python
# 检测 format_error 响应 → 路转到 tool_error
try:
    parsed = json.loads(out_str)
    if isinstance(parsed, dict) and parsed.get("success") is False:
        error_msg = parsed.get("error", "操作执行失败")
        await self._ws.send_json({"type": "tool_error", ...})
        return  # 不继续发送 tool_end
except (json.JSONDecodeError, TypeError):
    pass
```

同时在 `on_tool_error` 中也有独立的 `tool_error` 事件处理路线。

### 可维护性

**评估结果**：提取器系统存在一些**重复模式**值得关注：

1. **重复的 AST 解析逻辑**：`file_manage`、`file_search`、`file_edit`、`run_python` 等提取器中多次出现从 `tool_input` 中 `ast.literal_eval` 解析操作类型的逻辑。可提取为公共辅助函数：
   ```python
   def _parse_tool_input(tool_input: str | None) -> dict[str, Any] | None:
       """从工具输入字符串解析出参数字典。"""
       if not tool_input:
           return None
       try:
           parsed = ast.literal_eval(tool_input)
           return parsed if isinstance(parsed, dict) else None
       except (ValueError, SyntaxError, TypeError):
           return None
   ```

2. **嵌套的 POI/卡片遍历逻辑**：`nearby_search`、`fuzzy_address_search`、`get_transit_route`、`get_cycling_route`、`tarot`、`holiday_calendar` 等提取器中都包含手动多级遍历。对于稳定的嵌套结构，可考虑声明式转换模式（如 `dataclass` + `asdict` 映射）。

这些是代码组织层面的优化建议，不构成分层违规。
