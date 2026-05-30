# 记忆模块 — Long-Term Memory

```plantuml
@startuml

' ===== 样式设置 =====
skinparam classAttributeIconSize 0
skinparam backgroundColor #FEFEFE

' ===== 数据模型 =====

class MemoryItem {
  + description: str
  + theme: str
  + history: list[dict]
  + latest_update_time: str
  + update(reason, new_description, new_theme)
  + merge(another, reason, merged_description, merged_theme)
  + show_description_history() list[dict]
}

class MemoryManager {
  - _yaml_file: str
  + add(description, theme) str
  + delete(id) str
  + update(id, reason, new_description, new_theme)
  + merge(id1, id2, merged_description, merged_theme, reason)
  + show() list[dict]
  + show_description_history(id) list[dict]
  - _read_all() dict[str, MemoryItem]
  - _write_all(items)
  - _generate_id() str
  - _ensure_file_exists()
}

' ===== 异步管线 =====

class LongTermMemoryInterface {
  - _memory_path: Path
  - _mm: MemoryManager
  - _queue: asyncio.Queue | None
  - _consumer_task: asyncio.Task | None
  + is_listening: bool
  + start_listening(llm)
  + send_history(turn_messages)
  + stop_listening()
  + get_narrative() str
  - _consumer(llm)
}

' ===== CRUD 工具（模块级 @tool）=====

package "CRUD Tools (@tool)" {
  class create_memory_tool <<@tool>> {
    + content, section → str
  }
  class read_memories_tool <<@tool>> {
    + → str
  }
  class update_memory_tool <<@tool>> {
    + id, content, reason → str
  }
  class delete_memory_tool <<@tool>> {
    + id, reason → str
  }
  class merge_memories_tool <<@tool>> {
    + id1, id2, content, section, reason → str
  }
}

' ===== 系统提示词 =====

class ColdStartPrompt <<constant>> {
  + "冷启动：创建新分区并逐条添加记忆"
}

class UpdatePrompt <<constant>> {
  + "增量更新：对比新旧信息，增删改"
}

' ===== 初始化工具 =====

class UserInit {
  + {static} ensure_user_md()
  + {static} ensure_soul_md()
  + {static} ensure_env_file()
  + {static} ensure_all()
}

' ===== 格式化函数 =====

class Formatters {
  + {static} _format_narrative(items) str
  + {static} _format_entries_for_tool(items) str
  + {static} _format_messages(messages) str
}

' ===== 外部依赖 =====

class asyncio.Queue <<asyncio>> {
}

class portalocker.Lock <<portalocker>> {
}

class YAML_FILE <<memory.yaml>> {
}

class BaseChatModel <<langchain_core>> {
}

' ===== 关系 =====

MemoryManager --> MemoryItem : 管理全部条目
MemoryManager --> portalocker.Lock : 文件锁（进程安全）
MemoryManager --> YAML_FILE : 读写

LongTermMemoryInterface *-- MemoryManager : 持有
LongTermMemoryInterface *-- asyncio.Queue : 消息队列
LongTermMemoryInterface --> BaseChatModel : _consumer 使用 LLM 总结
LongTermMemoryInterface --> Formatters : 格式化输入输出

LongTermMemoryInterface --> ColdStartPrompt : 首次使用
LongTermMemoryInterface --> UpdatePrompt : 增量更新

CRUD Tools --> MemoryManager : 委托（通过 _current_mm）
CRUD Tools --> Formatters : 格式化输出

Formatters --> MemoryItem : 读取条目数据

UserInit --> YAML_FILE : 首次运行初始化

@enduml
```

## 包结构

```
memory/
├── __init__.py              # 空
├── narrative.py             # LongTermMemoryInterface + CRUD @tool + 格式化 + 提示词
├── memory_manager.py        # MemoryItem, MemoryManager（YAML CRUD + portalocker）
└── user_init.py             # 首次运行初始化：复制 USER.md / SOUL.md / .env
```

## 数据流

```
对话轮次结束
     ↓
LongTermMemoryInterface.send_history([...])
     ↓ (asyncio.Queue)
_consumer(llm)
     ├─ read_memories → MemoryManager.show()
     ├─ 选择 ColdStart / Update 提示词
     ├─ create_react_agent(llm, [create, read, update, delete, merge])
     ├─ agent.invoke()  →  CRUD @tool → MemoryManager  → memory.yaml
     └─ MemoryManager._write_all()  (portalocker 保护)
```

## 记忆存储格式

```
memory.yaml  (config/personas/)
  └─ UUID → {description, theme, history, latest_update_time}
```

每条记忆含唯一 ID、内容、分区（theme）、变更历史，通过 `portalocker` 实现进程安全的文件锁。
