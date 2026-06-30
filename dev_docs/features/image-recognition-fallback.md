# 图像认知：非多模态 LLM 的异常兜底机制

## 概述

"图像认知"特性将图片以 base64 编码的多模态内容形式注入 LLM 上下文（`HumanMessage(content=[{type:"text"},{type:"image_url",...}])`）。当目标 LLM 不支持多模态输入时，该特性需要一个健壮的降级路径，避免系统崩溃或状态损坏。

本文档说明现有的异常处理机制如何自然而然地兜住此类故障，并提供排查指引。

---

## 故障链路分析

### 正常路径

```
HumanMessage(content=[{type:"text"},{type:"image_url","image_url":{"url":"data:image/png;base64,..."}}])
  → agent.astream_events(inputs, config)
    → LangChain Provider 序列化（ChatOpenAI / 其他）
      → LLM API（支持多模态）→ 正常响应
```

### 非多模态 LLM 的故障点

```
HumanMessage(content=[{type:"text"},{type:"image_url",...}])
  → agent.astream_events(inputs, config)
    → LangChain Provider 序列化
      → 不支持 image_url → 抛出异常 ✗
```

异常发生的具体阶段：**序列化/API 调用阶段**，位于 `_stream_turn()` 的 `astream_events()` 内。LangChain 的 provider 集成层在序列化消息时，发现 model 不支持 `image_url` 内容类型，抛出 `ValueError` 或 `NotImplementedError`（取决于具体 provider 实现）。

### 异常传播路径

```
_stream_turn()  ←  astream_events() 抛出
  ↓  异常冒泡
_run_agent_turn()  ←  line 344: final_answer = await _stream_turn(...)
  ↓
except Exception as e:  ←  line 376
  ↓
print(f"[sub-agent] _run_agent_turn error: {e}", file=sys.stderr)
traceback.print_exc(file=sys.stderr)
  ↓
ws.send_json({type:"error", payload:{code:"AGENT_ERROR", message: str(e)}})
  ↓
finally:  ←  line 389
  → 发送 done 事件（含 context_usage / turn_id）
```

---

## 现有异常处理机制

`_run_agent_turn()` 在 `api/routes/chat.py` 中存在三层异常处理：

### 第一层：`asyncio.CancelledError`（line 360）

```python
except asyncio.CancelledError:
    interaction.cancel_all()
    await _inject_cancel_tool_messages(session, config, ws)
    await ws.send_json({"type": "error", "payload": {"code": "CANCELLED", ...}})
```

处理用户主动取消，与多模态无关。

### 第二层：`except Exception` — 全局兜底（line 376）

```python
except Exception as e:
    _run_error = str(e)
    print(f"[sub-agent:{session.session_id[:8]}] _run_agent_turn error: {e}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    await ws.send_json({
        "type": "error",
        "payload": {"code": "AGENT_ERROR", "message": str(e)},
    })
```

**这是非多模态 LLM 故障的实际兜底入口。** 特征：

- **范围**：捕获执行轮次中的所有非取消异常，包括多模态序列化失败、API 超时、token 超限等。
- **行为**：
  1. 将异常信息记录到 `stderr`（含完整 traceback）
  2. 向前端推送 `type: "error"` 事件，code 为 `AGENT_ERROR`
  3. 不中断流程，继续进入 `finally` 块

### 第三层：`finally` — 状态清理（line 389）

```python
finally:
    session._active_task = None
    context_usage = await _calculate_context_usage(...)
    turn_id = uuid.uuid4().hex
    await ws.send_json({"type": "done", "payload": {"turn_id": turn_id, "context_usage": context_usage}})
```

确保无论成功或失败，WebSocket 都会收到 `done` 事件，前端轮次状态正常终结，长期记忆（LTM）处理器不会悬挂。

---

## 用户端表现

当非多模态 LLM 遇到多模态内容时，用户看到：

1. **轮次正常结束**（发送按钮恢复可用）
2. **错误横幅**出现，包含类似以下消息：
   - `Content type 'image_url' is not supported by this model`
   - `The model `deepseek-v4-flash` does not support multimodal inputs`
   - 或 provider API 返回的原始错误描述
3. **对话历史不受影响** — 该轮次的 checkpoint 可能为空，但已有历史完整保留

### 前端错误渲染链路

```
WebSocket onmessage
  → handleEventForChannel() 中的 case 'error'
    → ch.error = event.payload.message
      → ch.isStreaming = false
        → ChatWindow 渲染 <div class="error-banner">{{ error }}</div>
```

`ChatWindow.vue`（line 83）中的错误横幅是一个纯文本条，显示在消息列表顶部。

---

## 哪些模型会触发此降级

从 `providers.yaml` 可知当前配置的模型：

| 模型 | 多模态支持 | 行为 |
|------|-----------|------|
| `deepseek-v4-flash` | ❌ 纯文本 | 触发 `AGENT_ERROR` |
| `deepseek-v4-pro` | ❌ 纯文本 | 触发 `AGENT_ERROR` |
| `qwen/qwen3.7-plus` | ✅ 支持 | 正常处理 |
| `z-ai/glm-5.2` | ❌ 纯文本 | 触发 `AGENT_ERROR` |
| `z-ai/glm-5v-turbo` | ✅ 支持 | 正常处理 |
| `mimo-v2.5-pro` | ⚠️ 取决于底层 API | 可能正常或触发降级 |
| `mimo-v2.5` | ⚠️ 取决于底层 API | 可能正常或触发降级 |

**注意**：`analyze_image` 工具始终使用 `z-ai/glm-5v-turbo`（通过独立 API 调用），与主聊天 LLM 无关。工具本身不受此降级影响。

---

## `HumanMessage` 多模态内容格式

当前实现构建的 `HumanMessage` 结构：

```python
content_parts = [
    {"type": "text", "text": "用户消息正文"},
    {"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0..."}},
    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,/9j/4AAQ..."}},
]
message = HumanMessage(content=content_parts)
```

此格式遵循 [OpenAI 多模态消息规范](https://platform.openai.com/docs/guides/vision)，LangChain 的 `ChatOpenAI` 集成层（`langchain_openai`）透传给支持多模态的 API。不支持此格式的 provider 在序列化阶段抛出异常。

---

## Provider 集成层的异常触发位置

以 `langchain_openai.ChatOpenAI` 为例，多模态内容失败的典型路径：

```
ChatOpenAI._generate()
  →  messages_to_openai() 序列化
    →  _convert_message_to_openai()
      →  HumanMessage.content 为 list
        →  遍历 content blocks
          →  遇到 {"type": "image_url"}
            →  检查 model 能力（部分 provider 在此校验）
            →  若不支持 → ValueError / API 400 错误
```

异常的具体类型和消息因 provider 集成而异：

- **OpenAI 兼容 API（DeepSeek / OpenRouter）**：调用 API 后返回 `400 Bad Request` → LangChain 将其包装为 `APIStatusError`（属于 `Exception` 子类）
- **其他 provider 集成**：可能在序列化阶段直接抛出 `ValueError`

由于 `_stream_turn` 使用 `graph.astream_events()` 执行，异常通过异步生成器传播，最终在 `_run_agent_turn` 的 `await _stream_turn(...)` 处被 `except Exception` 捕获。

---

## 为什么不需要专门处理

1. **`Exception` 范围足够覆盖** — 任何 provider 集成层的序列化/API 错误都是 `Exception` 子类，被第二层捕获。

2. **状态一致性强** — `finally` 块确保即使异常发生，也会发送 `done` 事件，前端轮次终结，`session._active_task` 清空，后续消息可正常发送。

3. **checkpoint 不损坏** — 异常发生在 `astream_events()` 内部，checkpoint 可能尚未写入，或仅写入部分状态。下一条消息的 `_run_agent_turn` 会新建 `inputs`，从 checkpointer 读取已有 checkpoint（不含损坏的当前轮次），继续正常运行。

4. **错误信息可读** — 原始异常消息直接转发给前端，用户能识别出"该模型不支持图片"并能采取行动（切换模型或关闭图像认知模式）。

---

## 调试指引

在 `stderr` 中搜索以下模式可快速定位问题：

```
[sub-agent:abc12345] _run_agent_turn error: ...
Traceback (most recent call last):
  ...
```

也可以直接搜索 `AGENT_ERROR` 在日志中的出现：

```bash
# 从后端日志中筛选图像认知相关的错误
grep "image_recognition\|image_url\|multimodal" <logs> --ignore-case

# 筛选所有代理错误
grep "AGENT_ERROR\|_run_agent_turn error" <logs>
```

---

## 潜在的改进方向

1. **发送前校验**：在构造多模态消息前，通过 provider 的 capability 表判断模型是否支持多模态。当前无此能力检测接口，LangChain `ChatOpenAI` 也未暴露此信息。

2. **自动降级到 analyze_image**：检测到多模态不被支持时，自动回退到通过 `analyze_image` 工具（GLM-5V-Turbo）处理图片，将文本描述注入上下文而非原始图片。这会增加一次 API 调用延迟，但体验更平滑。

3. **前端提示**：在用户激活图像认知按钮时，如果当前选择的模型已知不支持多模态，提前显示警告。需要在前端维护一个多模态模型名单。

4. **透传更多错误上下文**：当前 `str(e)` 在某些 provider 下可能不够精确。可以解析错误类型以区分"模型不支持"与其他错误（如超时），提供不同的 UI 反馈。

---

## 相关文件

| 文件 | 角色 |
|------|------|
| `api/routes/chat.py` | WebSocket 处理 + 异常兜底 |
| `tools/network/tool_image_understand.py` | 图片加载与 base64 编码（被复用） |
| `agent/graph.py` | Agent 图构建（`create_agent`） |
| `api/providers/openai_provider.py` | `ChatOpenAI` 封装 |
| `web/src/composables/useChat.ts` | 前端 WebSocket 事件处理（`case 'error'`） |
| `web/src/components/ChatWindow.vue` | 错误横幅渲染 |
| `providers.yaml` | 提供商与模型配置 |

---

*文档版本：v1.0 — 2026-06-30*
*对应特性："图像认知"按钮 — PR #[待定]*
