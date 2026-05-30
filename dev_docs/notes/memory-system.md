# 记忆系统（Memory System）

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    对外接口（不变）                        │
│  LongTermMemoryInterface                                │
│  get_narrative() / MEMORY_PATH                          │
├─────────────────────────────────────────────────────────┤
│                      narrative.py                        │
│  ┌─────────────────────────────────────────────────┐    │
│  │  CRUD 工具 (@tool)                              │    │
│  │  create_memory / read_memories                  │    │
│  │  update_memory / delete_memory                   │    │
│  │  通过 _current_mm 引用操作 MemoryManager         │    │
│  └─────────────────────────────────────────────────┘    │
│                          │                                │
│                          ▼                                │
│  ┌─────────────────────────────────────────────────┐    │
│  │          MemoryManager (memory_manager.py)       │    │
│  │  add / delete / update / show / load_yaml        │    │
│  │  save_yaml ←→ memory.yaml (YAML 持久化)          │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## 核心文件

| 文件 | 职责 |
|------|------|
| `memory/memory_manager.py` | 底层存储引擎，YAML 读写、条目 CRUD |
| `memory/narrative.py` | 上层接口，包含 LangChain 工具、异步消费管线、对外 API |
| `config/personas/memory.yaml` | 持久化文件（被 `.gitignore` 排除） |

## MemoryManager

`MemoryManager` 是一个通用的 YAML 持久化记忆存储器。

### MemoryItem

每条记忆是一个 `MemoryItem`，包含：

| 字段 | 说明 |
|------|------|
| `description` | 记忆内容（如"用户叫Miso"） |
| `theme` | 分类主题（如"身份""音乐"），对应旧系统的 section |
| `history` | 变更历史列表，每次 update 追加一条记录 |
| `latest_update_time` | 最近更新时间 |

### MemoryManager 方法

| 方法 | 说明 |
|------|------|
| `add(description, theme)` | 添加条目，返回 UUID |
| `delete(id)` | 删除条目，返回被删条目的 description |
| `update(id, reason, ...)` | 更新条目的 description/theme，记录变更原因 |
| `show()` | 返回 `[{id, description, theme}, ...]`，供工具和格式化使用 |
| `load_yaml()` | 从文件加载；文件不存在则创建空 YAML |
| `save_yaml()` | 持久化到文件 |

### 关键实现细节

- **ID 形式**：UUID4 字符串，由整理记忆 Agent 在单次调用周期内传递引用
- **Round-trip 正确性**：`MemoryItem.__init__` 从 kwargs 中正确提取 `history` 和 `latest_update_time`，避免序列化-反序列化后历史丢失

## 双重叙事格式

同一份数据通过两种格式化函数呈现，分别面向不同消费者：

### `_format_narrative()` — 给主 Agent 和网页端

只含 description 和 theme，**不含 id**：

```markdown
# 长期记忆索引
- [身份](#身份)
- [音乐](#音乐)

---

## 身份
- 用户叫Miso。

## 音乐
- 用户喜欢洛天依。
```

### `_format_entries_for_tool()` — 给整理记忆 Agent

含 description、theme 和 id：

```markdown
## 身份
  [a1b2c3d4-...] 用户叫Miso。

## 音乐
  [c3d4e5f6-...] 用户喜欢洛天依。
```

## 数据流

### 写入流程（`send_history` → 后台消费）

```
对话轮次结束
    │
    ▼
send_history(turn_messages)     ← 非阻塞入队
    │
    ▼
asyncio.Queue ──► _consumer()   ← 后台协程逐轮取出
    │
    ├─ 1. _set_current_mm(self._mm)    ← 挂载 MemoryManager 引用
    ├─ 2. self._mm.load_yaml()         ← 从磁盘加载最新状态
    ├─ 3. 构建 LangGraph ReAct Agent
    │      工具: create/read/update/delete_memory
    │      提示词: COLD_START_SYSTEM / UPDATE_SYSTEM
    ├─ 4. agent.ainvoke(user_prompt)   ← Agent 调用工具修改 _current_mm
    └─ 5. self._mm.save_yaml()         ← 持久化
```

### 读取流程

```
主 Agent 上下文构建                    网页端 GET /api/narrative
    │                                        │
    ▼                                        ▼
build_system_prompt()                  ltm.get_narrative()
    │                                        │
    ▼                                        ▼
get_narrative()  ← 模块级/实例方法，结果相同
    │
    ├─ MemoryManager(yaml_file).load_yaml()
    ├─ _format_narrative(mm.show())
    └─ 返回格式化叙事文本
```

## 对外接口（保持不变）

### `LongTermMemoryInterface`

| 方法 | 签名 | 说明 |
|------|------|------|
| `__init__` | `(memory_path: str \| Path)` | 接收 yaml 文件路径 |
| `get_narrative` | `() -> str` | 返回格式化叙事文本 |
| `start_listening` | `(llm)` | 启动后台消费管线 |
| `send_history` | `(turn_messages: list[dict])` | 异步入队（非阻塞） |
| `stop_listening` | `() -> None` | 排空队列并停止 |

### 模块级

- `MEMORY_PATH` — `config/personas/memory.yaml`
- `get_narrative()` — 等同 `LongTermMemoryInterface.get_narrative()`

## 与旧系统的区别

| 维度 | 旧系统 | 新系统 |
|------|--------|--------|
| 持久化格式 | 分区 Markdown（MEMORY.md） | YAML（memory.yaml） |
| ID 形式 | 自增整数（1, 2, 3...） | UUID4 |
| 内部存储 | MemoryStore（单例） | MemoryManager（实例） |
| 操作审计 | MemoryLogger（独立 YAML 日志） | MemoryItem.history（内嵌变更历史） |
| 序列化 | MemorySerializer（Markdown 解析/生成） | yaml.dump/safe_load |
