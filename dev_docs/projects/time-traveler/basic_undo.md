# Project TimeTraveler — 对话轮次撤回工程文档

## 一、项目概述

**Project TimeTraveler** 的目标是：在基于 LangGraph 的 Agent 应用中，提供一种干净、可预测的方式，撤回最近 N 轮对话。所谓"一轮"是指一次 **{ 用户输入 → [工具调用...] → LLM 最终回答 }** 的完整交互周期。

### 1.1 背景

LangGraph 的 `MemorySaver` 自动为每次 invoke 保存检查点。Agent 因此能记住历史。但有时用户需要"反悔"——撤回刚刚问过的问题、删除工具调用的记录、回退到某个更早的状态。三种场景最为常见：

| 场景 | 用户诉求 | 撤回粒度 |
|------|---------|---------|
| 问错问题 | "刚才那个问题我撤回，重新问" | 1 轮 |
| 批量反悔 | "最后那几轮对话没意义的，删掉" | N 轮 |
| 恢复上下文整洁 | "工具调用产生了太多脏消息，清掉" | 全部（回到初始） |

### 1.2 术语

- **轮（Round）**：一次完整的用户输入到最终回答。包含 1 条 `HumanMessage` + 0 到多条 `AIMessage`（含 tool_calls）+ 0 到多条 `ToolMessage` + 1 条最终 `AIMessage`。
- **检查点（Checkpoint）**：LangGraph 在每次节点执行后保存的状态快照。每个检查点包含当时完整的 `messages` 列表。
- **撤回（Undo）**：将当前线程的活跃消息列表恢复到指定轮次之前的状态，并让新的 invoke 基于此状态继续。

---

## 二、核心概念

### 2.1 add_messages Reducer 的工作方式

LangGraph 的状态管理依赖 **reducer 模式**。`messages` 字段使用的 reducer 是 `add_messages`。它按 `id` 决定如何处理新传入的消息：

| 传入内容 | `add_messages` 的行为 |
|---------|---------------------|
| 普通消息（HumanMessage / AIMessage / ToolMessage） | 按 `id` 去重。`id` 在已有列表中已存在则覆盖，不存在则追加 |
| **`RemoveMessage(id=xxx)`** | 在已有列表中查找对应 `id` 的消息，**直接删除** |
| 消息列表 | 依次对每条消息执行上述规则 |

```python
# RemoveMessage 的签名
class RemoveMessage(BaseMessage):
    """一条删除指令：告诉 reducer 要删除哪条消息。"""
    # 只需要 id，其他字段（content 等）全部忽略
```

这是整个 TimeTraveler 方案的底层支撑。

### 2.2 一轮对话的边界判定

一轮对话的起始边界是 **HumanMessage**。找到一条 HumanMessage，它之后（同一次 invoke 内）的所有消息都属于同一轮。

```
[invoke 1]          [invoke 2]          [invoke 3]
  H1                  H2                  H3        ← 用户输入
  A1 (tool_call)      A3 (final)          A5 (tc)
  T1 (tool_result)                           ...   ← 工具调用
  A2 (final)          ─── 轮次 2 ────      ─── 轮次 3 ───
  ─── 轮次 1 ────
```

撤回一轮 = 撤回一个 HumanMessage 及其之后的所有消息。

---

## 三、架构设计

### 3.1 接口设计

```
undo_last_round(agent, config)     → 撤回最近 1 轮
undo_rounds(agent, config, n)      → 撤回最近 n 轮
undo_all(agent, config)            → 撤回所有轮（清空）
```

所有函数共享同一套内部流程。

### 3.2 内部流程

```
                              ┌──────────────────┐
                              │   agent.get_state │
                              │   (config)        │
                              └────────┬─────────┘
                                       │
                                       ▼
                              ┌──────────────────┐
                              │ 取出 messages     │
                              │ 列表              │
                              └────────┬─────────┘
                                       │
                                       ▼
                              ┌──────────────────┐
                              │ 从后向前遍历，     │
                              │ 找到第 n 个       │
                              │ HumanMessage      │
                              └────────┬─────────┘
                                       │
                                       ▼
                              ┌──────────────────┐
                              │ 切片 messages[n:] │
                              │ 得到待删除列表    │
                              └────────┬─────────┘
                                       │
                                       ▼
                              ┌──────────────────┐
                              │ 构造 RemoveMessage│
                              │ 列表              │
                              └────────┬─────────┘
                                       │
                                       ▼
                              ┌──────────────────┐
                              │ agent.update_state│
                              │ (config, messages │
                              │  = remove_list)   │
                              └──────────────────┘
                                       │
                                       ▼
                              ┌──────────────────┐
                              │ 状态中该 HumanMsg │
                              │ 及之后消息已删除  │
                              │ ✓ 新 invoke 从此 │
                              │   基础上继续      │
                              │ ✓ 历史快照仍保留  │
                              └──────────────────┘
```

### 3.3 核心代码

```python
from langchain_core.messages import RemoveMessage


def undo_last_round(agent, config) -> int:
    """撤回最近一轮对话，返回删除的消息条数。"""
    state = agent.get_state(config)
    messages = state.values["messages"]

    # 从后往前找最后一个 HumanMessage
    last_human = None
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].type == "human":
            last_human = i
            break

    if last_human is None:
        return 0

    # 该 HumanMessage 及其之后所有消息都属于这一轮
    to_delete = messages[last_human:]

    # 提交删除指令
    agent.update_state(config, {
        "messages": [RemoveMessage(id=m.id) for m in to_delete]
    })
    return len(to_delete)


def undo_rounds(agent, config, n: int = 1) -> int:
    """撤回最近 n 轮对话，返回删除的消息条数。"""
    if n < 1:
        return 0

    state = agent.get_state(config) 
    messages = state.values["messages"]

    # 找出所有 HumanMessage 的位置
    human_indices = [i for i, m in enumerate(messages) if m.type == "human"]

    if len(human_indices) < n:
        # 不够 n 轮就全部删除
        to_delete = messages
    else:
        # 倒数第 n 个 human 的位置就是切割点
        cutoff = human_indices[-n]
        to_delete = messages[cutoff:]

    agent.update_state(config, {
        "messages": [RemoveMessage(id=m.id) for m in to_delete]
    })
    return len(to_delete)


def undo_all(agent, config) -> int:
    """撤回所有轮次，清空对话历史。"""
    return undo_rounds(agent, config, n=float("inf"))
```

---

## 四、如何使用

### 4.1 基本用法

```python
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import create_agent

checkpointer = MemorySaver()
agent = create_agent(model=llm, tools=[...], checkpointer=checkpointer)

config = {"configurable": {"thread_id": "session_1"}}

# 三轮对话
agent.invoke({"messages": [{"role": "user", "content": "我叫小明"}]}, config)
agent.invoke({"messages": [{"role": "user", "content": "我喜欢猫"}]}, config)
agent.invoke({"messages": [{"role": "user", "content": "北京天气怎么样"}]}, config)

# 撤回最后一轮（"北京天气怎么样" 及相关工具调用和回答）
deleted = undo_last_round(agent, config)
print(f"删除了 {deleted} 条消息")  # 可能包含 Human + AI + Tool + AI 共 4 条

# 现在 LLM 只记得"我叫小明"和"我喜欢猫"
result = agent.invoke(
    {"messages": [{"role": "user", "content": "我叫什么？我喜欢什么动物？"}]},
    config,
)
# → 你叫小明，你喜欢猫
```

### 4.2 批量撤回

```python
# 撤回最近两轮
deleted = undo_rounds(agent, config, n=2)
# 现在只剩第一轮了

# 撤回所有
deleted = undo_all(agent, config)
# 回到空白状态
```

### 4.3 撤回后重新问

撤回后 `invoke` 基于缩短后的消息列表执行。LLM 看不到被删掉的历史，但旧的历史快照仍然可以通过 `get_state_history` 访问。

```python
# 撤回后
undo_last_round(agent, config)

# 重新问
result = agent.invoke(
    {"messages": [{"role": "user", "content": "这次换个问题：上海天气怎么样？"}]},
    config,
)

# 旧历史还在检查点存储里，未丢失
history = list(agent.get_state_history(config))
print(f"共有 {len(history)} 个历史快照")
```

---

## 五、设计决策与约束

### 5.1 为什么用 `RemoveMessage` 而不是直接替换 messages

直接替换会被 `add_messages` reducer 按 `id` 去重，导致新旧消息混杂。`RemoveMessage` 是 reducer 原生支持的"删除指令"，语义明确、无副作用。

### 5.2 为什么以 HumanMessage 作为轮次边界

一轮对话总是由用户输入触发。HumanMessage 是每轮对话的唯一可靠入口标记。用 `AIMessage.tool_calls` 或时间戳都不可靠——工具调用可能不存在，时间戳精度不够。

### 5.3 撤回后历史去了哪里

撤回只是修改了当前活跃状态。旧的检查点仍可通过 `get_state_history` 获取。可以用 `update_state` 配合指定的 `checkpoint_id` 恢复到任意历史状态（Time Travel）。撤回不是删除，是**切换活跃分支**。

```
时间线（检查点不可变）:
  cp1 → cp2 → cp3 → cp4 → cp5 → cp6（当前）
                              │
                              └── 撤回一轮后：
                                  cp1 → cp2 → cp3 → cp4（新当前）
                                  （cp5 和 cp6 仍可通过 get_state_history 访问）
```

### 5.4 为什么用 `undo_rounds(agent, config, n=inf)` 而不是独立的 `undo_all`

避免重复实现。`n=inf` 意味着 `human_indices[-inf]` 实际上会落在 `human_indices[0]` 之前，触发 `len(human_indices) < n` 的分支，删除全部消息。也可以用 `n=10**9` 达到同样效果。

---

## 六、边界情况处理

| 情况 | 行为 |
|------|------|
| 线程为空（无任何消息） | 返回 0，无操作 |
| 线程中只有一条 HumanMessage | `undo_last_round` 删掉这一条及其回复，回到空状态 |
| 线程中有 HumanMessage 但无后续消息（invoke 尚未结束） | 正常删除该 HumanMessage |
| 请求撤回 N 轮，但历史不足 N 轮 | 全部删除，返回实际删除条数 |
| 撤回后立即 get_state_history | 旧检查点仍可访问 |
| 同一线程多次撤回 | 每次基于当前活跃状态的 human 位置重新计算 |

---

## 七、配套测试

### 7.1 单元测试结构

```python
# tests/test_time_traveler.py

import pytest
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver

from time_traveler import undo_last_round, undo_rounds


def test_undo_single_round_removes_correct_messages():
    """验证撤回一轮后，最后一条 HumanMessage 及其后续消息被删除。"""
    # 构造一个简单的图 + 三轮对话
    # 断言：撤回后消息数减少，且最后一条是撤回前倒数第二条 HumanMessage 的回答


def test_undo_two_rounds():
    """验证撤回两轮的正确性。"""


def test_undo_on_empty_thread_returns_zero():
    """空线程调用撤回应返回 0。"""


def test_undo_more_than_available_clears_all():
    """请求撤回超过已有轮次时，应清空并返回实际删除条数。"""


def test_history_preserved_after_undo():
    """撤回后 get_state_history 仍然能访问旧快照。"""


def test_new_invoke_builds_on_trimmed_history():
    """撤回后新的 invoke 应该基于截断后的历史，LLM 不记得已撤回的内容。"""
```

### 7.2 验收标准

- [ ] 撤回一轮后，下一轮 invoke 中 LLM 不记得被撤回的内容
- [ ] 撤回多轮后，下一轮 invoke 中 LLM 只记得未被撤回的内容
- [ ] 撤回全部后，下一轮 invoke 如同全新对话
- [ ] `get_state_history` 在撤回前后均能正常工作
- [ ] 高并发场景下（同一 thread 快速连续撤回+invoke）无竞态

---

## 八、与其他记忆机制的集成

| 机制 | 关系 |
|------|------|
| **MemorySaver（短期记忆）** | TimeTraveler 操作的对象。撤回修改的是 MemorySaver 管理的当前活跃状态 |
| **长时记忆（Store / 外部数据库）** | TimeTraveler 不涉及长期记忆。撤回对话历史不影响 Store 中的持久化记忆 |
| **消息摘要（Summarization）** | 如果对话中使用了摘要中间件（SummarizationMiddleware），撤回时摘要消息也会被保留或删除，取决于摘要消息是否在 HumanMessage 之前生成。需要额外处理 |
| **Time Travel（get_state_history 重放）** | 互补关系。Time Travel 从历史检查点重新执行，TimeTraveler 是主动裁切当前活跃状态 |

---

## 九、经验教训

### 9.1 不要在撤回后手动修改消息 id

```python
# ❌ 错误做法：自己构造新消息列表
state = agent.get_state(config)
old = state.values["messages"]
agent.update_state(config, {"messages": old[:3]})
# add_messages 会按 id 去重，新旧混杂，结果不可预测
```

```python
# ✅ 正确做法：用 RemoveMessage 表达删除意图
agent.update_state(config, {
    "messages": [RemoveMessage(id=m.id) for m in old[3:]]
})
```

### 9.2 `update_state` 不是原子的

在高并发场景下，连续两次 `update_state` 可能产生竞态。如果框架版本支持，考虑用 `checkpoint_id` 做乐观锁或加锁。

### 9.3 撤回不可逆

当前版本的撤回没有"反撤回"（redo）能力。如果需要，可以通过保留撤回前的 `checkpoint_id` 并用 `update_state` 指向该检查点来实现。
