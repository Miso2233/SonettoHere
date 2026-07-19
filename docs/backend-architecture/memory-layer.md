# 长期记忆层 (memory/)

## 层级定位

**第⑥层 — 长期记忆层**。与 `session/` 会话管理层并列，位于 Provider 抽象层（第⑤层）之下，核心基础设施层（第⑦层）之上。通过 `@tool` 暴露给 Agent 编排层（第③层）使用，同时提供 REST 接口复用。

```
③ Agent 编排层 ─── @tool ────────────► ⑥ memory/  (CRUD 操作)
② 路由层 ───────── REST ─────────────► ⑥ memory/  (REST 复用)
⑥ memory/ ─────── create_llm() ─────► ⑤ providers/ (后台叙事 LLM 调用)
```

## 模块文件清单

| 文件/目录 | 职责 |
|-----------|------|
| `manager/base.py` | **BaseMemoryManager** — 抽象基类，定义 _load_all / _save_all 原语 + show / get_memories_grouped / _generate_id 默认实现 |
| `manager/yaml.py` | **YamlMemoryManager(BaseMemoryManager)** — YAML 文件持久化 CRUD，portalocker 文件锁并发安全；**MemoryManagerBuilder** — 构造器，统一建造形式 |
| `long_term.py` | **LongTermMemory** — 后台 LLM 增量总结管线 + 5 个模块级 `@tool`；Builder → inject_all() 统一注入管理器到所有消费方 |
| `callback.py` | MemoryToolCallback — CRUD 工具事件 → WebSocket 前端推送 |
| `short_term.py` | **短期记忆管理器** — 全局 MemorySaver 单例，所有会话的 LangGraph 检查点共享此实例，通过 `thread_id = session.session_id` 区分隔离 |
| `user_init.py` | 首次运行初始化：USER.md / SOUL.md / .env 文件复制 |

> **长期记忆 vs 短期记忆**：`memory/` 层管理两种不同生命周期的记忆。长期记忆（`manager/yaml.py` + `long_term.py`）通过 LLM 总结写入 YAML，跨会话持久化。短期记忆（`short_term.py`）管理运行时对话上下文（MemorySaver 检查点），跟随会话生命周期，过期即清理。

## 职责描述

### 1. 记忆的 CRUD 存储

`BaseMemoryManager` 是抽象接口，定义 `_load_all()` / `_save_all()` 两个原语，并在其上实现 `show()`、`get_memories_grouped()`、`show_description_history()` 等通用方法。`YamlMemoryManager` 是 YAML 后端的实现，提供增（add）、删（delete）、改（update）、合并（merge）方法，使用 `portalocker` 文件锁保证多进程并发安全。

构造方式通过 `MemoryManagerBuilder` 统一：

```python
mm = MemoryManagerBuilder() \
    .with_backend(YamlMemoryManager, yaml_file="config/personas/memory.yaml") \
    .build()
```

### 2. LLM 驱动的记忆叙事与总结

`LongTermMemory` 是异步管线：每轮对话消息 → `asyncio.Queue` → 后台 LLM CRUD Agent → `memory.yaml` 写入。实现了冷启动（首次无记忆）和增量更新（已有记忆）两种叙事策略。

应用启动时通过 `inject_all()` 将 `LongTermMemory` 持有的管理器注入到所有需要 mm 的地方：

```python
ltm = LongTermMemory(MemoryManagerBuilder().with_backend(...).build())
ltm.start_listening()
ltm.inject_all()   # → _set_current_mm() + tools/memory inject_memory_manager()
```

### 3. 首次运行环境初始化

`user_init.py` 在应用启动时调用 `ensure_all()`，确保 USER.md、SOUL.md、.env 等必要文件存在，不存在时从 `.example` 模板复制。

## 关键代码片段

### 继承体系

```
BaseMemoryManager (抽象基类)
├── _load_all()          ← 抽象原语
├── _save_all()          ← 抽象原语
├── _generate_id()       ← 默认实现：secrets.token_hex(4)
├── show()               ← 遍历 _load_all → [{id, description, theme}]
├── show_description_history()  ← 查找 → MemoryItem.show_description_history()
├── get_memories_grouped()      ← 分组 + 排序
│
└── YamlMemoryManager (YAML 后端)
    ├── _load_all()      ← yaml.safe_load
    ├── _save_all()      ← yaml.dump
    ├── add / delete / update / merge  ← portalocker 事务
    └── MemoryItem        ← 数据模型，在 base.py 中定义
```

### YamlMemoryManager 核心 CRUD + 文件锁

```python
# api/memory/manager/yaml.py

class YamlMemoryManager(BaseMemoryManager):
    def __init__(self, yaml_file: str):
        self._yaml_file = yaml_file
        self._ensure_file_exists()

    def add(self, description: str, theme: str) -> str:
        """新增记忆条目。使用 portalocker 文件锁保证并发安全。"""
        with portalocker.Lock(self._lock_path, timeout=5):
            items = self._load_all()
            new_id = self._generate_id()
            items[new_id] = MemoryItem(description, theme)
            self._save_all(items)
        return new_id

    def delete(self, id: str) -> str:
        """删除条目，返回删除的描述文本。"""
        with portalocker.Lock(self._lock_path, timeout=5):
            items = self._load_all()
            if id not in items:
                raise ValueError(f"YamlMemoryManager: Memory item with ID {id} not found")
            removed = items.pop(id)
            self._save_all(items)
        return removed.description

    def update(self, id: str, reason: str,
               new_description: str | None = None,
               new_theme: str | None = None):
        """更新条目，记录变更原因和历史。"""
        with portalocker.Lock(self._lock_path, timeout=5):
            items = self._load_all()
            if id not in items:
                raise ValueError(f"YamlMemoryManager: Memory item with ID {id} not found")
            items[id].update(reason, new_description, new_theme)
            self._save_all(items)

    def merge(self, id1: str, id2: str,
              merged_description: str, merged_theme: str, reason: str):
        """合并两条记忆，保留完整修改历史。"""
        with portalocker.Lock(self._lock_path, timeout=5):
            items = self._load_all()
            if id1 not in items or id2 not in items:
                raise ValueError(...)
            items[id1].merge(items[id2], reason, merged_description, merged_theme)
            items.pop(id2)
            self._save_all(items)
```

文件锁机制：
- 使用 `portalocker.Lock` 对 `.lock` 文件加互斥锁，超时时间 5 秒
- 所有读写操作均在锁保护范围内执行
- 支持多进程/多线程并发安全

### 模块级 @tool 定义

```python
# api/memory/long_term.py

@tool
def create_memory(content: str, section: str) -> str:
    """添加一条新的记忆条目到指定分区。"""
    content = _sanitize(content)
    if len(content) > MAX_DESC_LENGTH:
        return f"驳回：记忆内容超过 {MAX_DESC_LENGTH} 字限制..."
    if _current_mm is None:
        return "错误：记忆管理器未初始化。"
    new_id = _current_mm.add(description=content, theme=section)
    return f"已创建 [{new_id}] ({section}): {content}"

@tool
def read_memories() -> str:
    """查看当前所有记忆条目及其 ID 和分区。"""
    if _current_mm is None:
        return "（暂无记忆条目）"
    return _format_entries_for_tool(_current_mm.show())

@tool
def update_memory(id: str, content: str, reason: str) -> str:
    """根据 ID 更新一条已有记忆。"""
    ...

@tool
def delete_memory(id: str, reason: str) -> str:
    """根据 ID 删除一条记忆。"""
    ...

@tool
def merge_memories(id1: str, id2: str, content: str, section: str, reason: str) -> str:
    """将两条相似记忆合并为一条。"""
    ...
```

这些 `@tool` 函数通过模块级全局变量 `_current_mm` 委托给 `BaseMemoryManager` 实例，由 `LongTermMemory.inject_all()` 在启动时注入。

### tools/memory/ 工具

六个记忆 `ToolBase` 子类（`tool_create_memory.py` 等）不自行构造 `YamlMemoryManager`，而是通过 `tools/memory/__init__.py` 的 `get_memory_manager()` 获取注入的共享管理器：

```python
# tools/memory/tool_create_memory.py
def _run(self, ...):
    from tools.memory import get_memory_manager
    mm = get_memory_manager()
    new_id = mm.add(description=content, theme=section)
    ...
```

注入在应用启动时由 `LongTermMemory.inject_all()` 统一完成：

```
LongTermMemory.inject_all()
  ├── _set_current_mm(self._mm)         → 给 long_term.py 模块级 @tool
  └── inject_memory_manager(self._mm)   → 给 tools/memory/ 六个 Tool
```

## 设计要点

### 文件锁保证并发安全

所有 `YamlMemoryManager` 的写操作（add / delete / update / merge）都通过 `portalocker.Lock` 保护，读操作（show / show_description_history / get_memories_grouped）基于 `_load_all()` 实现，锁由 CRUD 方法自行管理。锁文件 (`.lock`) 与数据文件 (.yaml) 同路径，超时 5 秒。

```python
@property
def _lock_path(self) -> str:
    return self._yaml_file + ".lock"
```

### YAML 持久化

- 数据以 `dict[id → MemoryItem.__dict__]` 的格式写入 YAML
- `_load_all` / `_save_all` 是对 YAML 文件的唯二读写入口
- ID 生成：`secrets.token_hex(4)` → 8 字符十六进制（旧版 UUID 格式由迁移脚本 `scripts/migrations/uuid-to-hex-id.py` 一次性转换）
- `MemoryItem` 在 `base.py` 中定义，提供 `show_description_history()` 历史追溯

### 后台总结不阻塞聊天

`LongTermMemory` 采用**生产者-消费者**异步管线：

```
send_history(user_msg)           — 生产者，非阻塞放入队列
    │
    ▼
Queue[ (session_id, turn_id, messages), ... ]
    │
    ▼
_consumer()                      — 后台协程，逐条消费
    │
    ├── _set_current_mm(mm)     — 兜底注入（主注入已在 inject_all() 完成）
    ├── create_agent(llm, tools) — 创建 CRUD Agent
    ├── agent.ainvoke(...)       — LLM 调用
    ├── callback.py              — 推送 tool 事件到前端
    └── memory.yaml              — 持久化写入
```

- 聊天响应直接返回用户，不等待记忆总结完成
- 后台消费者的 LLM 调用复用同一个 Provider 提供的 `BaseChatModel`
- 支持 `stop_listening()` 安全关闭（`None` 哨兵）

## 分层边界

### 对外暴露方式

| 使用方 | 接口方式 | 具体入口 |
|--------|----------|----------|
| Agent 编排层（long_term.py） | `@tool` 函数 | `create_memory` / `read_memories` / `update_memory` / `delete_memory` / `merge_memories` |
| Agent 编排层（tools/memory/） | `ToolBase` 子类 | `ListMemoriesTool` / `ReadMemoriesTool` / `CreateMemoryTool` / `UpdateMemoryTool` / `DeleteMemoryTool` / `MergeMemoriesTool` |
| REST 路由层 | `LongTermMemory._mm` 方法 | `/api/long-term`、`/api/memories`、`/api/moment` |
| Vignette 前端 | REST API | `/api/memories` 端点返回分组记忆（`get_memories_grouped`） |
| Agent 工具层 | `get_narrative()` | 读取完整记忆叙事文本，作为系统提示前缀 |
| 查询相关 | `get_related_memory_from()` | 基于 LLM 的语义检索 |

### 依赖关系

| 依赖方向 | 目标模块 | 说明 |
|----------|----------|------|
| `long_term.py →` | `manager/` | BaseMemoryManager + YamlMemoryManager + Builder |
| `long_term.py →` | `callback.py` | MemoryToolCallback |
| `long_term.py →` | `api.session.manager` | SessionState（`session.get_messages()` 提取消息） |
| `long_term.py →` | `api.session.manager` | session_manager（通过 `session_manager.get(sid).ws` 获取 WebSocket） |
| `long_term.py →` | `tools/memory/` | inject_all() 注入管理器实例 |
| `callback.py →` | `api.session.manager` | session_manager（通过 `session_manager.get(sid).ws` 获取 WebSocket） |
| `short_term.py →` | `langgraph.checkpoint.memory` | MemorySaver 全局单例 |
| `api.session.manager →` | `short_term.py` | `get_checkpointer()` / `delete_thread()` — 会话层倒依赖短期记忆模块 |
| `long_term.py →` | `api.providers` | 通过 `create_agent` 间接调用（LLM 由外部注入） |

### 设计约定评估

**已知问题**：

1. **模块级全局变量**：`long_term.py` 中的 `_current_mm` 是模块级可变全局状态，通过 `_set_current_mm()` 注入。`inject_all()` 在启动时设置一次，`_consumer` 中每次迭代兜底再设一次。单消费者场景下工作正常，但若并发存在多个 `LongTermMemory` 实例（如多租户），全局状态会互相覆盖。建议改为实例级别的依赖注入，使 `@tool` 函数与具体的 `BaseMemoryManager` 实例绑定。

2. **Session 依赖方向**：`long_term.py` 和 `callback.py` 都通过 `api.session.manager.session_manager` 访问会话状态。`api.session.manager` 也反向依赖 `memory/short_term.py` 获取全局 checkpointer。这属于同一层级（第⑥层）内的模块间依赖，不违反分层规则。但应注意：`session/` 与 `memory/` 同层，彼此引入时需要避免循环依赖（当前 `short_term.py` 不依赖 `session/`，所以无风险）。

3. **模块级 @tool 的测试性**：`@tool` 函数是模块级函数而非类方法，无法在单元测试中轻松替换 `_current_mm`。模块级 `get_narrative()`（带 `lru_cache`）仍硬编码 `MEMORY_PATH` 作为回退路径。

**改进建议**：
- 将 `@tool` 函数改为类方法或工厂函数，通过闭包绑定 `BaseMemoryManager` 实例，消除全局可变状态。
- 或者使用 `contextvars` 为每个异步任务独立管理 `_current_mm`，支持多实例并发。