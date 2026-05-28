# ReAct Agent 核心原理

## 什么是 ReAct

**ReAct**（Reasoning + Acting）是一种让 LLM 交替进行"推理"与"行动"的 Agent 范式。LLM 不是一次性给出最终答案，而是：

1. **推理（Thought）**：分析当前已知信息，决定下一步做什么
2. **行动（Action）**：调用一个外部工具，传入参数
3. **观察（Observation）**：接收工具返回的结果
4. 回到步骤 1，直到信息足够，输出最终答案

这个循环使得 LLM 从"纯粹的文字生成器"升级为"能与外部世界交互的智能体"。

---

## ReAct 循环的四个阶段

```
┌──────────┐    工具调用结果    ┌──────────┐
│  Thought │ ──────────────→ │  Action  │
│  推理分析 │ ←────────────── │  执行工具 │
└──────────┘    Observation   └──────────┘
      │                            │
      │ 信息充足时                    │
      ▼                            ▼
┌──────────┐               ┌──────────┐
│  Answer  │               │  Error?  │
│  最终回答 │               │ 重试/修正 │
└──────────┘               └──────────┘
```

### 1. Thought（推理）

LLM 接收用户输入和当前对话历史，分析还缺什么信息、应该调用哪个工具、参数是什么。推理是**内部过程**，用户不可见，但它决定了后续行动的质量。

在本项目中，推理过程通过 `PrinterCallback.on_llm_new_token` 以青色（Cyan）流式输出到终端，让用户看到 Agent 的思考过程。

### 2. Action（行动）

LLM 以 **tool_call** 的形式发出行动指令。这不是 LLM 自己执行代码，而是 LLM 输出一个结构化 JSON（符合 OpenAI function calling 规范），由 LangGraph 框架捕获并路由到对应的工具函数。

本项目中每个 Skill 就是一个可供调用的工具，其输入参数由 Pydantic `BaseModel` 严格校验。

### 3. Observation（观察）

工具函数执行完毕后，返回结果被包装为 `ToolMessage` 追加到消息列表中，LLM 在下一轮推理中可以看到这个结果。Observation 由系统自动生成，LLM 不应自行编造。

### 4. Answer（回答）

当 LLM 判断信息已经足够回答用户问题时，它不再发出 tool_call，而是直接生成自然语言文本。此时 ReAct 循环终止，回答返回给用户。

---

## 本项目中的 ReAct 实现

### LangGraph 的 `create_react_agent`

在 [agent/graph.py](../agent/graph.py) 中，核心只有一行：

```python
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

checkpointer = MemorySaver()

graph = create_react_agent(
    model=model,          # ChatOpenAI 实例（DeepSeek）
    tools=tools,          # 30 个 Skill 的列表
    state_schema=AgentState,  # 自定义状态结构
    prompt=system_prompt,     # 系统提示词
    checkpointer=checkpointer,  # 会话状态持久化
)
```

`create_react_agent` 在内部构建了一个 LangGraph 状态图，它自动实现了以下逻辑：

1. 将用户消息追加到 `AgentState.messages`
2. 调用 LLM（带 tools 绑定），LLM 返回 `AIMessage`（含 `tool_calls` 或纯文本）
3. 如果 `AIMessage` 包含 `tool_calls`：
   - 逐一执行对应的工具函数
   - 将每个工具返回结果包装为 `ToolMessage`
   - 回到步骤 2
4. 如果 `AIMessage` 是纯文本（无 `tool_calls`）：
   - 循环终止，文本即为最终回答

### 递归限制（recursion_limit）

```python
graph.with_config({"recursion_limit": 120})
```

`recursion_limit` 是 LangGraph 的安全阀。它限制了一个回合中 LLM ↔ Tool 往返的最大次数（默认 25，本项目设为 120）。如果 Agent 陷入循环（反复调用同一个工具），超过限制后 LangGraph 会抛出 `GraphRecursionError`，阻止无限消耗 token。

---

## OpenAI Function Calling 与 ReAct 的关系

ReAct 是一个**概念范式**，而 OpenAI function calling 是**实现该范式的具体协议**。两者的对应关系：

| ReAct 概念 | OpenAI Function Calling 实现 |
|------------|------------------------------|
| Thought | LLM 内部推理（体现在决定调用哪个 function） |
| Action | `tool_calls` 数组中的 function name + arguments |
| Observation | `ToolMessage`（role="tool"） |
| Answer | `AIMessage` 不含 tool_calls，content 为自然语言 |

本项目使用 DeepSeek Chat 作为 LLM 后端，它兼容 OpenAI 的 function calling 协议，因此 LangChain 的 `ChatOpenAI` 类可以直接对接。

---

## 一次完整的 ReAct 循环示例

以"帮我查明天北京的天气，如果下雨就提醒我带伞"为例：

```
第 1 轮：
  LLM Thought:  用户需要天气信息，先调用 time_skill 获取"明天"的具体日期
  Action:        time_skill()
  Observation:   {"date": "2026-05-10", ...}

第 2 轮：
  LLM Thought:  明天是5月10日，现在调用天气查询
  Action:        get_current_weather(city="北京", forecast=true)
  Observation:   {"forecast": [{"date":"2026-05-10","weather":"小雨","temp":"18~22℃"}]}

第 3 轮：
  LLM Thought:  明天有小雨，我需要提醒用户带伞
  Answer:        "Miso，明天（5月10日）北京预计有小雨，气温18~22℃，记得出门带把伞哦～"
```

可以看到，Agent 自主决定了调用顺序（先获取日期，再查天气），并根据结果做出了合理判断（下雨→提醒带伞）。

---

## ReAct 的优势与局限

**优势：**

- **可解释性**：每一步思考过程可见，调试方便
- **工具组合**：LLM 可以灵活组合多个工具解决复杂问题
- **容错性**：工具调用失败时可以换参数重试或换工具

**局限：**

- **延迟**：每调用一个工具就多一次 LLM API 往返，多步任务延迟成倍增加
- **Token 消耗**：每轮推理都需要携带完整的历史消息，长对话成本高
- **循环风险**：LLM 可能陷入重复调用相同工具的循环（需 recursion_limit 兜底）
- **幻觉工具**：LLM 可能"发明"不存在的工具或参数（需 Pydantic 校验拦截）

本项目的解决思路：
- **延迟**：简单 Skill（如 `time_skill`）不强制先读文档，减少不必要往返
- **Token**：`ShortTermMemory` 基于 tiktoken 自动裁剪超出部分
- **循环**：`recursion_limit=120` + `AGENTS.md` 中明确的"禁止重复调用"规则
- **幻觉**：Pydantic `BaseModel` 在框架层面校验参数类型，非法调用直接被拒绝

---

## 下一节

[LangGraph 状态图与状态管理](02-LangGraph状态图与状态管理.md) — 深入理解 `StateGraph` 的内部机制、`AgentState` 结构设计和 `MemorySaver` 的持久化策略。
