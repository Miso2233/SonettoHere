# 上下文用量估算失效调查报告

## 一、现象

Agent 读取 dev_docs 目录全部文件（~25k tokens）后，前端上下文用量从 15.4k 仅升至 16.1k，增量约 700 tokens。

## 二、根因

`_calculate_context_usage()` 调用 `checkpointer.aget_state()`，但当前 LangGraph 版本（1.1.10）中 `InMemorySaver` **不存在此方法**。异常被 `except Exception: counting_messages = []` 静默捕获，导致每次计算返回 0 条消息。

此前端看到的 15.4k → 16.1k 实际完全来自 `system_prompt` 自身 token（约 16.5k），从未包含任何对话消息。

## 三、代码追溯

### 数据流

```
file_operations._read_file()
  → 返回 format_success({"content": data, ...})      # JSON 字符串，含全文
  → LangGraph 创建 ToolMessage(content=该JSON字符串)
  → add_messages reducer 追加到 AgentState.messages
  → MemorySaver checkpointer 持久化完整消息 ✓
  → _calculate_context_usage()
    → checkpointer.aget_tuple(config)                  # 旧版：aget_state() → AttributeError ✗
    → counting_messages = []                            # 异常被静默吞掉
    → estimate_context_usage(messages=[])               # 始终传空列表
```

### LangGraph API 变更

| 版本 | 方法 | 返回值 |
|------|------|--------|
| 0.x（旧） | `aget_state(config)` | 对象，含 `.values` 字典 |
| 1.x（当前 1.1.10） | `aget_tuple(config)` | `CheckpointTuple`，含 `.checkpoint["channel_values"]` |

### 修复

```python
# 修复前（静默异常）
state = await checkpointer.aget_state(config)
counting_messages = state.values.get("messages", [])

# 修复后
cpt = await checkpointer.aget_tuple(config)
if cpt is not None:
    channel_values = cpt.checkpoint.get("channel_values", {})
    counting_messages = channel_values.get("messages", [])
```

## 四、影响

- **上下文用量始终显示为 system_prompt 大小**（约 16.5k tokens），不随对话增长
- 上下文裁剪、超出限制等逻辑基于此数据决策，实际已**完全失效**
- 贡献给 `usage_percent` 的分子恒为 system_prompt tokens，分母为 `model_context_window`（256k），显示占比始终在 6-7%，不反映真实上下文压力

## 五、相关文件

| 文件 | 说明 |
|------|------|
| `api/routes/chat.py` | `_calculate_context_usage()` 使用错误 API |
| `api/context_usage.py` | `estimate_context_usage()` 本身逻辑正确，但收到的消息列表为空 |
| `api/session_manager.py` | `SessionState.checkpointer` 定义为 `MemorySaver`，实际为 `InMemorySaver` |

## 六、原始文章修正

前文 `context-usage-toolcall-gap.md` 关于 `tool_calls` / `ToolMessage` 元数据遗漏的偏差分析（~16%偏差）在理论上成立，但实践中该偏差被 checkpointer API 不兼容导致的**100%偏差**所掩盖——消息从未进入计数函数，而非计数函数漏算。
