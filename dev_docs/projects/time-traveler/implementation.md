# TimeTraveler 撤回功能实现文档

## 概述

本文档记录 TimeTraveler 撤回功能的实现细节，作为 [basic_undo.md](basic_undo.md) 设计文档的落地配套。

### 功能目标

在 SonettoHere 的对话界面中，用户可以通过右键菜单撤回自己发送的最后一条消息（及其对应的工具调用和 AI 回复），使对话状态回退到上一轮之前。

---

## 架构变更

### 数据流

```
用户右键最后一条消息 → 菜单「撤回」
  → ChatWindow emit('action', {action:'undo'})
    → ChatView handleUndo()
      → api.undoMessages(sessionId)          [HTTP POST]
        → sessions.py undo endpoint
          → time_traveler.undo_rounds(graph, config)
            → graph.aget_state()               [读取当前消息列表]
            → 定位最后一个 HumanMessage
            → 构造 RemoveMessage 列表
            → graph.aupdate_state()            [提交删除指令]
          ← { deleted_count: N }
      ← response
    → useChat.removeTurns(1)                  [前端移除最后一条 turn]
    → UI 自动更新
```

### 后端设计决策

#### 为什么用 `CompiledStateGraph` 而不是直接操作 checkpointer

设计文档原本提议通过 `agent.get_state()` / `agent.update_state()` 操作状态。在 SonettoHere 中，Agent 图每次在 `_run_agent_turn` 中构建，未持久化在 session 上。

**方案**：在 `SessionState` 中新增 `_graph` 字段，`build_agent()` 后将编译图缓存到 session 上。撤回端点通过 `session._graph` 调用 `aget_state` / `aupdate_state`。

**优势**：
- 无需每次重建图（轻量）
- 复用图的 state schema，确保 `add_messages` reducer 正确处理 `RemoveMessage`
- 避免绕开 reducer 直接操作 checkpointer 可能导致的状态不一致

#### 为什么用 REST 而非 WebSocket

撤回是"一次性命令"语义（send-and-forget），无需流式推送，用 REST POST 更简洁。同时避免与正在进行的 WebSocket 消息序列产生耦合。

---

## 文件变更清单

### 新增文件

| 文件 | 说明 |
|------|------|
| `api/time_traveler.py` | 撤回核心逻辑：`undo_rounds()` / `undo_last_round()` / `undo_all()` |
| `web/src/assets/icons/context-menu/undo-arrow.svg` | 撤回图标（Material Design undo 风格） |

### 修改文件

| 文件 | 改动 |
|------|------|
| `api/session_manager.py` | `SessionState` 新增 `_graph` 字段，存储编译图引用 |
| `api/routes/chat.py` | `_run_agent_turn` 中 `build_agent()` 后缓存 `session._graph` |
| `api/routes/sessions.py` | 新增 `POST /sessions/{id}/undo` 端点 |
| `web/src/components/Icon.vue` | 注册 `undo-arrow` 图标 |
| `web/src/components/ChatWindow.vue` | 上下文菜单动态计算，用户消息追加「撤回」项 |
| `web/src/composables/useChat.ts` | 新增 `removeTurns(count)` 方法 |
| `web/src/api/index.ts` | 新增 `undoMessages(sessionId, n)` API 方法 |
| `web/src/views/ChatView.vue` | 处理撤回事件，调 API + 更新 turns |

---

## 撤回逻辑详解 (`api/time_traveler.py`)

```python
async def undo_rounds(graph, config, n=1):
    state = await graph.aget_state(config)
    messages = state.values["messages"]

    # 找出所有 HumanMessage 位置
    human_indices = [i for i, m in enumerate(messages) if m.type == "human"]

    if len(human_indices) < n:
        to_delete = messages              # 不够 n 轮则全部删除
    else:
        cutoff = human_indices[-n]         # 倒数第 n 个人类消息
        to_delete = messages[cutoff:]     # 该消息及之后全部删除

    # RemoveMessage 被 add_messages reducer 识别并删除
    await graph.aupdate_state(config, {
        "messages": [RemoveMessage(id=m.id) for m in to_delete]
    })
```

### 轮次边界

一轮对话定义为：**一条 HumanMessage 及其之后的所有消息**（包括 AI 回复、工具调用等）。撤回 N 轮 = 从倒数第 N 条 HumanMessage 开始截断。

### 边界情况

| 场景 | 行为 |
|------|------|
| 无消息 | 返回 0，无操作 |
| 无 HumanMessage | 返回 0，无操作 |
| 请求 N 轮超出历史 | 清空全部消息 |
| 撤回时图正在执行 | 状态通过同一个 checkpointer 更新，LangGraph 检查点机制保证一致性 |

---

## 前端交互细节

### 上下文菜单控制 (`ChatWindow.vue`)

`ctxMenuItems` 从静态数组改为 **`computed`**，条件判断：

```typescript
const ctxMenuItems = computed(() => {
  const items = [
    { label: '引用', action: 'cite', icon: 'cite-speech' },
    { label: '复制', action: 'copy', icon: 'copy' },
  ]
  // 仅在右键最后一条已完成的用户消息时显示
  if (
    sourceType === 'user_message'
    && userMsgIdx === turns.length - 1
    && turns.length > 0
  ) {
    items.push({ label: '撤回', action: 'undo', icon: 'undo-arrow' })
  }
  return items
})
```

### 状态同步

撤回成功后，前端直接操作 turns 数组移除最后一条：

```typescript
function removeTurns(count: number) {
  ch.turns.splice(ch.turns.length - count, count)
  persistTurns(sessionId)      // 同步 localStorage
  refreshSessions()            // 刷新会话列表
}
```

注意：撤回操作**不通过 WebSocket** 推送，删除 turn 后 Vue 响应式系统自动更新 UI。

---

## 测试指南

### 人工验证

1. 发送多条消息形成多轮对话
2. 右键最后一条用户消息 → 出现「撤回」选项
3. 点击撤回 → 最后一条消息消失，对话回退到上一轮
4. 右键 AI 消息或工具结果 → 菜单不含「撤回」
5. 发送新消息 → 新对话基于撤回后的历史继续

### 异常场景

- **空会话**：右键无消息区域不应触发菜单
- **撤回 + 新消息连续操作**：新消息应基于截断后的历史
- **撤回后刷新页面**：localStorage 中的 turns 已同步移除，刷新后不回弹

---

## 后续可能的扩展

- **多轮撤回**：后端已支持 `n` 参数，前端可以扩展为「撤回 N 轮」或「撤回至该条」
- **Redo/反撤回**：通过保留撤回前的 `checkpoint_id` 实现恢复
- **系统提示**：撤回后追加一条系统消息提示"已撤回一条消息"
