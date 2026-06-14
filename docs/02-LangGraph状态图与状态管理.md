# LangGraph 状态图与状态管理

## 为什么需要状态图

普通的 LLM 调用是**无状态**的：每次请求都需要携带全部历史消息。而 Agent 需要在多轮工具调用中保持上下文——LLM 调用了什么工具、工具返回了什么结果、已经完成了多少步推理。这些信息必须在整个 ReAct 循环中持续可用。

LangGraph 通过**状态图（StateGraph）**解决了这个问题：它将 Agent 的一次运行建模为状态在图节点之间的流转，节点可以读写共享状态，边定义流转规则。

---

## AgentState: 状态的骨架

在 [agent/state.py](../agent/state.py) 中定义了 `AgentState`：

```python
from typing import Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    remaining_steps: int
```

### `messages` 字段

这是 Agent 的**核心状态**——所有对话消息的序列。类型为 `Annotated[Sequence[BaseMessage], add_messages]`，其中 `add_messages` 是 LangGraph 提供的**reducer 函数**，定义了如何处理状态更新。

一个典型的消息序列：

```python
messages = [
    SystemMessage(content="你是 Sonetto..."),
    HumanMessage(content="明天北京天气怎么样？"),
    AIMessage(content="", tool_calls=[{"name": "get_current_weather", "args": {...}}]),
    ToolMessage(content='{"success": true, "data": {...}}', name="get_current_weather"),
    AIMessage(content="明天北京晴转多云，18~25℃..."),
]
```

`add_messages` reducer 的行为：
- 新消息直接**追加**到列表末尾
- 如果消息带有相同 ID（更新已有消息），则**原地替换**
- 这个行为使得状态更新是增量且幂等的

### `remaining_steps` 字段

LangGraph 内置的步数计数器。每完成一次 LLM 推理或工具调用会递减。当 `remaining_steps <= 0` 时，图执行终止，防止无限循环。`recursion_limit=120` 设置的就是这个字段的初始值。

---

## `create_react_agent` 的内部结构

`create_react_agent` 是 LangGraph 提供的预构建函数。它内部创建了一个包含两个节点的状态图：

```
┌──────────────┐     tool_calls 存在    ┌──────────────┐
│   agent 节点  │ ──────────────────→ │  tools 节点   │
│  (调用 LLM)   │ ←────────────────── │ (执行工具函数) │
└──────────────┘    返回 ToolMessage    └──────────────┘
       │                                      │
       │ 无 tool_calls（纯文本）                │
       ▼                                      │
   ┌──────┐                                   │
   │ END  │                                   │
   └──────┘                                   │
```

### agent 节点

- 接收当前 `AgentState`
- 用绑定了 tools 的 LLM 模型处理 `messages`
- LLM 返回 `AIMessage`
  - 如果含 `tool_calls`：图路由到 `tools` 节点
  - 如果不含 `tool_calls`（纯文本）：图终止，返回回答

### tools 节点

- 接收 `AIMessage` 中的 `tool_calls`
- 逐一匹配并执行对应的工具函数
- 将每个执行结果包装为 `ToolMessage`，追加到状态中
- 图路由回 `agent` 节点（继续推理）

### 条件边

agent 节点后的路由由一条**条件边**决定：检查 `AIMessage` 是否包含 `tool_calls`。包含 → 进入 tools 节点；不包含 → 结束。

---

## `build_agent` 封装分析

在 [agent/graph.py](../agent/graph.py) 中，`build_agent` 函数完成了组装：

```python
def build_agent(
    model: BaseChatModel,
    tools: list[BaseTool],
    system_prompt: str,
    recursion_limit: int = 120,
) -> CompiledStateGraph:
    checkpointer = MemorySaver()

    return create_react_agent(
        model=model,
        tools=tools,
        state_schema=AgentState,
        prompt=system_prompt,
        checkpointer=checkpointer,
    ).with_config({"recursion_limit": recursion_limit})
```

### 参数说明

| 参数 | 类型 | 说明 |
|------|------|------|
| `model` | `BaseChatModel` | 绑定了 tools 的 LLM 实例。本项目使用 `ChatOpenAI(model="deepseek-v4-flash")` |
| `tools` | `list[BaseTool]` | 工具列表。本项目为 `get_all_tools()` 返回的 30 个 Skill |
| `state_schema` | `AgentState` | 自定义状态类型（含 `messages` + `remaining_steps`） |
| `prompt` | `str` | 系统提示词字符串，被包装为 `SystemMessage` 追加到消息列表头部 |
| `checkpointer` | `MemorySaver` | 内存级状态持久化器，下文详解 |

### `with_config` 的作用

```python
.with_config({"recursion_limit": recursion_limit})
```

LangGraph 的 `.with_config()` 在编译后的图上设置运行时配置。`recursion_limit` 指定了一个回合中图节点之间的最大跳转次数。对于涉及多步工具调用的复杂任务（如"帮我规划周末出行" → 查天气 → 查路线 → 查周边），120 次递归限制提供了足够的操作空间。

---

## MemorySaver: 状态持久化

```python
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()
```

`MemorySaver` 是 LangGraph 内置的内存级检查点存储。每次图执行后，完整的 `AgentState` 被保存到一个 `thread_id` 对应的槽位中。同一 `thread_id` 的下次调用会恢复之前的状态，实现**跨回合的对话连续性**。

### 在本项目中的使用

```python
config = {"configurable": {"thread_id": self.session_id}}

async for event in self.graph.astream_events(
    {"messages": [{"role": "user", "content": user_input}]},
    config=config,
    version="v2"
):
    ...
```

- 每个会话（CLI 启动一次）生成一个唯一的 `session_id` 作为 `thread_id`
- 同一会话的所有轮次共享同一个 `thread_id`，因此所有历史消息都被保留
- 用户执行 `/clear` 时重置会话（但 `MemorySaver` 中的数据仍存在，新 session_id 会创建新槽位）

### `MemorySaver` 的局限性

- **纯内存存储**：进程退出后所有状态丢失
- **无持久化**：不适合需要跨进程重启保持对话的场景
- **无限增长**：长对话的消息历史持续累加，直到 `ShortTermMemory` 裁剪

对于教学和本地使用，这些限制是可接受的。生产环境可换用 `SqliteSaver` 或 `PostgresSaver`。

---

## 流式事件机制

本项目使用 LangGraph 的 `astream_events` API（v2 版本）来实时获取 Agent 内部的执行情况：

```python
async for event in self.graph.astream_events(inputs, config=config, version="v2"):
    kind = event["event"]
    name = event.get("name", "")

    if kind == "on_chat_model_start":    # LLM 开始推理
        ...
    elif kind == "on_chat_model_stream": # LLM 流式输出 token
        ...
    elif kind == "on_chat_model_end":    # LLM 推理完成
        ...
    elif kind == "on_tool_start":        # 工具开始执行
        ...
    elif kind == "on_tool_end":          # 工具执行完成
        ...
    elif kind == "on_tool_error":        # 工具执行出错
        ...
    elif kind == "on_chain_end":         # Agent 链结束（最终输出）
        ...
```

这些事件类型覆盖了 ReAct 循环的每一个关键节点，WebSocket 回调利用它们在浏览器实时呈现：

- 青色（Cyan）→ LLM 思考过程
- 品红（Magenta）→ Skill 调用
- 绿色（Green）→ Skill 执行结果
- 白色（White）→ 最终回答

---

## 核心概念映射

| LangGraph 概念 | 本项目实现 | 文件 |
|---------------|-----------|------|
| `StateGraph` | `create_react_agent` 内部创建 | [agent/graph.py](../agent/graph.py) |
| State Schema | `AgentState(TypedDict)` | [agent/state.py](../agent/state.py) |
| Reducer | `add_messages`（LangGraph 内置） | — |
| Node | `agent` 节点 + `tools` 节点 | `create_react_agent` 内部 |
| Conditional Edge | 检查 `AIMessage.tool_calls` 是否存在 | `create_react_agent` 内部 |
| Checkpointer | `MemorySaver` | [agent/graph.py:19](../agent/graph.py) |
| Recursion Limit | `30` | [agent/graph.py:27](../agent/graph.py) |
| Streaming | `astream_events(version="v2")` | [graph.py](../agent/graph.py) |

---

## 下一节

[Tool 与 Skill 系统](03-Tool与Skill系统.md) — 深入分析 30 个 Skill 的基类设计、`get_doc` 两步调用模式、Pydantic 参数校验和 `SharedAPIClient` 的复用策略。
