# WebSocket 层 — 实时对话与工具回调

```plantuml
@startuml

' ===== 样式设置 =====
skinparam classAttributeIconSize 0
skinparam backgroundColor #FEFEFE

' ===== WebSocket 回调 =====

class WebSocketCallback <<BaseCallbackHandler>> {
  - _ws: WebSocket
  - _thinking_started: bool
  - _tool_start_time: dict[str, float]
  - _tool_names: dict[str, str]
  - _tool_inputs: dict[str, str]
  + on_llm_start()
  + on_llm_new_token(token)
  + on_llm_end(response)
  + on_tool_start(serialized, input_str)
  + on_tool_end(output)
  + on_tool_error(error)
  + {static} _extract_tool_data(tool_name, output, tool_input) dict | None
}

' ===== 工具提取器注册表 =====

class Registry {
  + {static} register(tool_name) Callable
  + {static} register_prefix(prefix) Callable
  + {static} _dispatch(tool_name, parsed, tool_input) dict | None
}

class Handler <<Callable>> {
  + (tool_name, parsed, tool_input) → dict | None
}

' ===== 提取器示例 =====

class extract_bilibili <<@register>> {
  + video_title, cover_url, file_path, quality
}

class extract_tarot <<@register>> {
  + question, spread_type, cards, ...
}

class extract_weather <<@register>> {
  + city, temp, condition, humidity, wind
}

class extract_word <<@register_prefix("word_")>> {
  + tool_type, action, success, message, ...
}

' ===== 交互注册表 =====

class InteractionRegistry {
  + {static} register(meta) str
  + {static} consume_future(interaction_id) Future | None
  + {static} resolve(interaction_id, response) bool
  + {static} cleanup(interaction_id)
}

' ===== 上下文用量估算 =====

class ContextUsage {
  + {static} count_tokens(text) int
  + {static} estimate_context_usage(messages, system_prompt, max_tokens, model_name) dict
}

' ===== WebSocket 端点 =====

class WebSocketEndpoint {
  + {static} websocket_chat(ws, session_id)
  + {static} _run_agent_turn(ws, session, user_message, private_mode, provider_id, model_name)
  + {static} _stream_turn(graph, inputs, config, ws, session, system_prompt) str
  + {static} _calculate_context_usage(session, system_prompt, model_name) dict
  + {static} _get_final_answer(event) str
}

' ===== 外部依赖 =====

class BaseCallbackHandler <<langchain_core>> {
}

class WebSocket <<fastapi>> {
}

class asyncio.Future <<asyncio>> {
}

' ===== 关系 =====

WebSocketCallback -|> BaseCallbackHandler : extends

WebSocketCallback --> Registry : 调用 _dispatch
Registry o-- Handler : 注册表持有

Handler <|.. extract_bilibili : 实现
Handler <|.. extract_tarot : 实现
Handler <|.. extract_weather : 实现
Handler <|.. extract_word : 实现

WebSocketEndpoint --> WebSocket : 接收/发送消息
WebSocketEndpoint --> WebSocketCallback : 创建实例
WebSocketEndpoint --> ContextUsage : 计算用量
WebSocketEndpoint --> InteractionRegistry : 处理用户交互

InteractionRegistry o-- asyncio.Future : pending 交互

@enduml
```

## 包结构

```
api/
├── routes/
│   └── chat.py               # WebSocket 端点 + Agent 编排
├── callbacks/
│   ├── websocket_callback.py  # WebSocketCallback（LangChain → JSON 推送）
│   └── tool_extractors.py     # 工具提取器注册表 + 各工具 Strategy
├── interaction.py             # 用户交互注册表（ask_user 挂起/唤醒）
└── context_usage.py           # token 计数与上下文估算
```

## WebSocket 消息流

```
Client → /ws/chat/{session_id}
  │
  ├─ "chat"  → _run_agent_turn()
  │              ├─ WebSocketCallback.on_llm_start()       → "thinking_start"
  │              ├─ WebSocketCallback.on_llm_new_token()   → "token"
  │              ├─ WebSocketCallback.on_llm_end()         → "thinking_end"
  │              ├─ WebSocketCallback.on_tool_start()      → "tool_start"
  │              ├─ WebSocketCallback.on_tool_end()         → "tool_end" (+ tool_data)
  │              ├─ WebSocketCallback.on_tool_error()      → "tool_error"
  │              └─ ...                                     → "answer" + "done" + "context_usage"
  │
  ├─ "cancel" → cancel agent_task
  ├─ "ping"   → "pong"
  └─ "user_response" → InteractionRegistry.resolve()
```
