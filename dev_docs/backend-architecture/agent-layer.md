# Agent 编排层 (api/agent/)

## 层级定位

**第③层 — Agent 编排层**，后端的核心大脑。

位于路由层之下、提供商抽象层之上，是整个后端的神经中枢。它不处理具体业务逻辑，而是负责编排 LLM 对话轮次的完整生命周期：

1. 接收上层（路由层）的用户消息
2. 调度 LLM 调用和工具执行
3. 流式输出中间结果
4. 管理交互挂起/唤醒流程
5. 后处理（记忆持久化、会话保存）

## 模块文件清单

| 文件 | 职责 | 主要类型/函数 |
|---|---|---|
| `turn.py` | Agent 对话编排：构建 Agent 图、流式执行、取消处理、记忆持久化 | `_LlmConfig`, `_TurnContext`, `_TurnResult`, `run_agent_turn()` |
| `interaction.py` | 交互注册表：管理 ask_user 系列工具的挂起与唤醒 | `register()`, `resolve()`, `cancel_all()` |
| `events/turn.py` (TurnSender) | 从 api/events/ 导入的 Agent 轮次事件发送器 | `TurnSender` |
| `context_usage.py` | 上下文窗口 token 用量估算（基于 tiktoken） | `count_tokens()`, `estimate_context_usage()` |
| `time_traveler.py` | 对话轮次撤回（基于 RemoveMessage 机制） | `undo_rounds()`, `undo_last_round()`, `undo_all()` |

### 核心数据结构

**`_LlmConfig`** — LLM 实例及上下文窗口配置：

| 字段 | 类型 | 说明 |
|---|---|---|
| `llm` | `BaseChatModel` | LangChain 聊天模型实例 |
| `model_name` | `str` | 当前使用的模型名称（如 `gpt-4o`、`deepseek-chat`） |
| `max_tokens` | `int` | 模型最大上下文窗口大小（token 数） |

> `_LlmConfig` 通过 `_resolve_llm()` 构建，内部调用 `provider_manager.get_model_metadata()` 统一查询模型上下文窗口、视觉能力等元数据，替代了之前分散在各处的内联 `model_vision` 检测。

**`_TurnContext`** — 一轮 Agent 执行所需的全部上下文（构建后不可变）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `system_prompt` | `str` | 当前会话的系统提示词 |
| `agent` | `Sonetto` | 编译后的 LangGraph Agent（绑定全局 MemorySaver 单例） |
| `inputs` | `dict[str, list[HumanMessage]]` | 本轮输入消息 |
| `config` | `dict[str, Any]` | 运行配置（`thread_id`、`callbacks`、`recursion_limit`） |

**`_TurnResult`** — 一轮 Agent 执行的结果：

| 字段 | 类型 | 说明 |
|---|---|---|
| `final_answer` | `str` | Agent 产出的最终文本回答（空串表示无回答） |
| `turn_id` | `str` | UUID hex，用于关联记忆事件 |
| `error` | `str \| None` | 执行过程中抛出的异常；成功时为 `None` |

## 职责描述

### 1. 编排 LLM 对话轮次

- 解析 LLM 配置（模型选择、上下文窗口参数）：通过 `provider_manager.get_model_metadata()` 统一查询模型上下文窗口和多模态能力
- 构建 LangGraph Agent 图（`Sonetto`），注入工具、系统提示、全局 checkpointer
- 流式执行 Agent 图，收集最终回答
- 后处理：消息计数、LTM 持久化、Const 会话保存、Sub-agent 回调

### 2. 管理工具调用与交互流程

- 提供 `interaction.py` 交互注册表，使工具函数能挂起等待用户确认
- 使用 `asyncio.Future` 实现挂起/唤醒，保证非阻塞
- 任务取消时统一清理所有挂起的交互

### 3. 流式输出处理

- 基于 `graph.astream_events()` 逐事件消费 Agent 图输出
- LLM token 通过回调层实时推送到前端
- 工具执行结束自动推送上下文用量更新

### 4. Token 用量估算

- 基于 `tiktoken` 估算对话上下文的 token 消耗
- 支持图片 token 估算（多模态场景）
- 提供系统提示词细分（`breakdown`），便于前端可视化

## 关键代码片段

### Agent 图构建（`turn.py`）

```python
async def _build_turn_context(
    tools: list,
    session: SessionState,
    llm_conf: _LlmConfig,
    user_message: str,
    image_recognition: bool,
    image_refs: list[str] | None,
) -> _TurnContext:
    """构建 Agent 图、输入消息和执行配置。"""
    system_prompt = build_system_prompt()
    cb_sender = CallbackSender.from_context()
    ws_callback = WebSocketCallback(cb_sender)

    agent = build_agent(
        model=llm_conf.llm,
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=get_checkpointer(),   # 全局 MemorySaver 单例
    )
    session.set_graph(agent)

    # 多模态输入处理
    if image_recognition and image_refs:
        content_parts: list[dict] = [{"type": "text", "text": user_message}]
        for img_path in image_refs:
            # ... 图片加载与 base64 编码 ...
        inputs = {"messages": [HumanMessage(content=content_parts)]}
    else:
        inputs = {"messages": [HumanMessage(content=user_message)]}

    config = {
        "configurable": {"thread_id": session.session_id},
        "callbacks": [ws_callback],
        "recursion_limit": 120,
    }

    return _TurnContext(system_prompt, agent, inputs, config)
```

**关键变更**：
- `checkpointer=session.checkpointer` → `checkpointer=get_checkpointer()`：所有会话共享同一个 MemorySaver 全局单例，通过 `thread_id = session.session_id` 区分隔离
- `CallbackSender.from_ws(ws)` → `CallbackSender.from_context()`：回调发送器不再从参数接收 `ws`，改为从 `contextvars` 自动获取当前轮次的 WebSocket

### 流式执行（`turn.py`）

```python
async def _stream_turn(
    graph: Sonetto,
    inputs: dict[str, list[HumanMessage]],
    config: dict[str, Any],
    sender: TurnSender,
    session: SessionState,
    system_prompt: str,
    model_name: str | None = None,
    max_tokens: int = 256_000,
) -> str:
    """流式执行 Agent 图，返回最终回答。"""
    final_answer = ""
    async for event in graph.astream_events(inputs, config=config, version="v2"):
        if event.get("event") == "on_chain_end" and event.get("name") == "agent":
            final_answer = _get_final_answer(event)
        # 工具执行完毕，推送上下文用量
        if event.get("event") == "on_chain_end" and event.get("name") == "tools":
            usage = await estimate_context_usage_from_session(...)
            await sender.context_usage(usage)

    # 兜底：从 checkpoint 提取
    if not final_answer:
        # ... checkpoint 读取逻辑 ...
    return final_answer
```

### 交互注册表（`interaction.py`）

**挂起机制** — 工具函数通过 `register()` 创建 Future 并返回 `interaction_id`：

```python
# 全局待处理交互表：interaction_id → Future
_pending: dict[str, asyncio.Future] = {}

def register() -> tuple[str, asyncio.Future]:
    """注册一次待处理的用户交互，返回 (interaction_id, future)。"""
    interaction_id = uuid.uuid4().hex
    future: asyncio.Future = asyncio.Future()
    _pending[interaction_id] = future
    return interaction_id, future
```

**唤醒机制** — 前端通过 WebSocket 送达 `user_response` 事件，路由层调用 `resolve()`：

```python
def resolve(interaction_id: str, response) -> bool:
    """用用户响应结果唤醒并解决挂起的 Future。返回是否成功。"""
    future = _pending.get(interaction_id)
    if not future or future.done():
        return False
    future.set_result(response)
    return True
```

**任务取消清理** — 当 Agent 任务被取消时，统一将所有挂起的交互标记为已完成：

```python
def cancel_all(reason: str | None = None):
    """将所有挂起的交互 Future 以取消原因标记为已完成。"""
    if reason is None:
        reason = "用户取消了该工具调用"
    formatted = format_error(reason)
    for interaction_id, future in list(_pending.items()):
        if not future.done():
            future.set_result(formatted)
        _pending.pop(interaction_id, None)
```

### 轮次撤回（`time_traveler.py`）

基于 LangGraph 的 `RemoveMessage` 机制，通过 `update_state` 删除 checkpoint 中的历史消息：

```python
async def undo_rounds(graph, config, n: int = 1) -> int:
    state = await graph.aget_state(config)
    messages = state.values.get("messages", [])

    human_indices = [i for i, m in enumerate(messages) if m.type == "human"]
    if len(human_indices) < n:
        to_delete = messages  # 不够 n 轮就全部删除
    else:
        cutoff = human_indices[-n]
        to_delete = messages[cutoff:]

    await graph.aupdate_state(
        config, {"messages": [RemoveMessage(id=m.id) for m in to_delete]}
    )
    return len(to_delete)
```

## 数据流 — 完整聊天轮次

```
用户消息
    │
    ▼
路由层 (routes/chat.py)
    │ 解析 WebSocket 事件类型 → chat
    │
    ▼
run_agent_turn()                    ← 顶层编排入口
    │
    ├── 阶段 1: _resolve_llm()
    │   │  provider_manager.get_model_metadata()  ← 统一查询上下文窗口 + 多模态
    │   │  provider_manager.create_llm() / 回退 default_llm
    │   │  返回 _LlmConfig (llm + model_name + max_tokens)
    │   ▼
    ├── 阶段 2: _build_turn_context()
    │   │  build_system_prompt() → system_prompt
    │   │  CallbackSender.from_context() → WebSocketCallback → 注入 LangChain 事件链路
    │   │  build_agent(checkpointer=get_checkpointer()) → graph
    │   │      │ 全局 MemorySaver 单例，thread_id = session.session_id 隔离
    │   │  处理多模态输入（图片 base64 编码）
    │   │  ToolManager.get_all(multimodal=image_recognition)  ← 按需过滤工具集
    │   │  返回 _TurnContext (system_prompt, agent, inputs, config)
    │   ▼
    ├── 阶段 3: _execute_agent_turn()
    │   │  ┌─ context_usage 初始用量推送
    │   │  │       │
    │   │  │       ▼
    │   │  │  _stream_turn()
    │   │  │       │
    │   │  │       ▼
    │   │  │  graph.astream_events()  ──→  回调层 (WebSocketCallback)
    │   │  │       │                          │
    │   │  │       │                          ├── on_llm_start  → "thinking_start"
    │   │  │       │                          ├── on_llm_new_token → "token" (流式文本)
    │   │  │       │                          ├── on_llm_end    → "thinking_end"
    │   │  │       │                          ├── on_tool_start → "tool_start"
    │   │  │       │                          ├── on_tool_end   → "tool_end" (+ tool_data)
    │   │  │       │                          └── on_tool_error → "tool_error"
    │   │  │       │
    │   │  │       ▼
    │   │  │  on_chain_end("agent") → final_answer 提取
    │   │  │  on_chain_end("tools") → context_usage 刷新 → sender
    │   │  │
    │   │  │  * CancelledError → interaction.cancel_all() → _inject_cancel_tool_messages()
    │   │  │  * Exception      → sender.error("AGENT_ERROR", ...)
    │   │  │
    │   │  └─ sender.done(turn_id, context_usage)  ← 轮次结束
    │   ▼
    └── 阶段 4: _postprocess_turn()
        │  session.increment_messages()
        │  ltm.send_history_from_session()     ← 记忆持久化（非私密模式）
        │  save_const_session()                ← Const 会话保存
        │  处理 Sub-agent pending 回调结果
        ▼
    _TurnResult (final_answer, turn_id, error)
        │
        ▼
    路由层 → WebSocket 响应完成
```

## 设计要点

### 事件驱动

- 整个编排层基于事件驱动：LangGraph `astream_events()` 产生事件流 → 回调层转换为 WebSocket 事件 → 前端实时渲染
- 工具执行与 LLM 生成通过 LangGraph 图结构自然编排，无需手动调度

### 异步流式

- 全程异步：`async for` 消费事件，`await` 发送 WebSocket 消息
- 流式 token 通过 `on_llm_new_token` 实时推送，用户边看边等
- `TurnSender` 封装统一的消息结构 `{"type": ..., "payload": ...}`

### 可中断

- `asyncio.CancelledError` 捕获后执行优雅取消流程：
  1. 取消所有挂起的用户交互（`interaction.cancel_all()`）
  2. 为孤立的 `tool_calls` 注入格式化的 `ToolMessage`（checkpoint 一致性）
  3. 通知前端对应工具气泡进入错误状态
- `_inject_cancel_tool_messages()` 确保下一条消息不会触发 `"tool_calls without corresponding ToolMessage"` 错误

### 关注点分离

- `run_agent_turn()` 为唯一公共入口，内部按 4 个阶段分步执行
- 各阶段独立为私有函数（`_resolve_llm`, `_build_turn_context`, `_execute_agent_turn`, `_postprocess_turn`），职责单一
- 数据对象（`_LlmConfig`, `_TurnContext`, `_TurnResult`）在各阶段之间传递，避免共享可变状态

### 模型元数据统一查询（PR #248）

`ProviderManager.get_model_metadata(model_name)` 将之前分散在各处的模型元数据查询集中管理：

```python
# api/providers/manager.py
def get_model_metadata(self, model_name: str) -> dict:
    """返回模型上下文窗口、视觉能力等元数据。"""
    return {
        "context_window": ...,
        "vision": ...,
    }
```

- `_resolve_llm()` 通过此方法统一获取上下文窗口和多模态信息，替代了之前 `create_llm()` 返回三元组的内联检测
- `create_llm()` 简化，仅返回 `BaseChatModel | None`

### 工具集按需过滤（PR #248）

`ToolManager.get_all(multimodal: bool | None = None)` 支持根据当前会话是否需要多模态能力来过滤工具集：

```python
# api/tools/manager.py
def get_all(self, multimodal: bool | None = None) -> list[BaseTool]:
    """获取工具列表，multimodal=True 时仅保留多模态工具，False 时排除。"""
```

- `multimodal=True`：仅保留需要视觉输入的工具（如 `read_image`），配合图片理解场景
- `multimodal=False`：排除多模态工具（非图片会话不暴露图片相关工具）
- `multimodal=None`（默认）：返回全部工具，保持向后兼容

## 设计约定评估

### 依赖方向

**约定**：Agent 编排层（第③层）可依赖第⑤⑥⑦层，不可依赖第②层或第④层。

**评估结果**：基本合规，但有**一处轻微违例**：

**违规项：`turn.py` 直接导入 `WebSocketCallback`**
- `turn.py` 导入 `from api.callbacks.websocket_callback import WebSocketCallback`
- 这是第③层直接导入第④层的符号，违反"下层不依赖上层"（实际是平行层级的逆向依赖）
- **影响**：虽然目前无循环导入风险（回调层不依赖 agent 层），但这种依赖模糊了层级边界。如果未来重构回调层，agent 层需相应修改。

**改进建议**：
1. **接口注入**：`_build_turn_context()` 应将 `WebSocketCallback` 作为参数接收，而非自行构造
2. 或在 `turn.py` 中定义回调接口协议（Protocol），由路由层注入具体实现，彻底切断直接导入

### 异常处理边界

**约定**：编排层应捕获所有异常，不向上抛裸异常。

**评估结果**：合规。`_execute_agent_turn()` 中：
- `CancelledError` → 优雅取消流程
- `Exception` → 捕获后 `sender.error()`，存入 `_TurnResult.error`
- `finally` → 始终清理 `active_task` 并推送 `done` 事件

### 数据流完整性

**约定**：每一轮对话的执行上下文应在轮次结束时完整持久化。

**评估结果**：合规。`_postprocess_turn()` 中：
- 非私密模式 → LTM 持久化
- Const 会话 → `save_const_session()`
- 消息计数 → `session.increment_messages()`
