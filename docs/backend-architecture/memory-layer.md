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
| `manager/base.py` | **BaseMemoryManager** — 抽象基类，定义 _load_all / _save_all / _write_lock 三个原语 + 完整 CRUD 默认实现 + show / get_memories_grouped / _validate_all_items / _generate_id |
| `manager/yaml.py` | **YamlMemoryManager(BaseMemoryManager)** — YAML 文件持久化，仅实现 _load_all / _save_all / _write_lock + 介质相关 self_check |
| `manager/builder.py` | **MemoryManagerBuilder** — 构造器，统一建造形式，与后端解耦 |
| `long_term.py` | **LongTermMemory** — 核心编排器：后台持久化管线（V6 起记忆读取改由 `memory_search` 工具承担） |
| `consumer.py` | **MemoryConsumer** — 后台 CRUD Agent 管线 + 模块级 `@tool`（create_memory / read_memories / update_memory / delete_memory / merge_memories / hit_memory）；`set_current_mm()` 公开注入 |
| `search.py` | **记忆精确搜索** — 主题 + 正则命中，并沿 `related` 用多源 BFS 推导多级关联闭包；纯逻辑模块，供 `memory_search` 工具与测试复用 |
| `callback.py` | MemoryToolCallback — CRUD 工具事件 → WebSocket 前端推送 |
| `review.py` | **记忆写入复核登记表** — TECH/PROJECT/MOMENT 主题的新建写入登记为待决项，前端弹卡片让用户「批准保留 / 拒绝撤销」 |
| `theme.py` | V6 九大语义主题的唯一权威源：`MemoryTheme` / `THEME_LABELS` / `VALID_THEMES` / `REVIEW_THEMES` + 校验与展示函数 |
| `short_term.py` | **短期记忆管理器** — 全局 MemorySaver 单例，所有会话的 LangGraph 检查点共享此实例，通过 `thread_id = session.session_id` 区分隔离 |
| `user_init.py` | 首次运行初始化：USER.md / SOUL.md / .env 文件复制 |

> **长期记忆 vs 短期记忆**：`memory/` 层管理两种不同生命周期的记忆。长期记忆（`manager/yaml.py` + `long_term.py`）通过 LLM 总结写入 YAML，跨会话持久化。短期记忆（`short_term.py`）管理运行时对话上下文（MemorySaver 检查点），跟随会话生命周期，过期即清理。

## 职责描述

### 0. 记忆写入复核（`review.py`）

后台记忆 LLM 新建 **TECH（技术事实与结论）/ PROJECT（学业与创作产出）/ MOMENT（事件与经历）**
三类主题的条目时，内容往往带判断与事实性结论，写错用户很难察觉。这三类写入照常落盘，但会
登记为待决项推给前端，在「记忆回调」小图标下方弹出卡片，由用户决定**批准保留**还是**拒绝撤销**
（撤销即 `mm.delete(id)`）。

因为 `delete` 是 `add` 的精确逆运算（两者都只改 `related`，都不动其他条目的
`latest_update_time`），撤销不需要任何快照 / 回滚机制。触发范围仅限 `create_memory`，
`merge_memories` / `update_memory` / `delete_memory` / `link_memories` 不参与。

管线分两段，原因是**同步工具无法 `await`**：

```
create_memory 工具（LangChain 线程池执行，无 running loop）
  └── review.record_create(id, desc, theme)        → 纯内存登记草稿
MemoryConsumer.consume()
  ├── 方法开头  drain_drafts()                      → 丢弃上一轮可能的残留
  └── finally  drain_drafts() → publish() → WS 推送 → memory_done
```

三个必须遵守的约束：

1. **`drain_drafts()` 的「取出 + 清空」必须在同一把锁内原子完成**。同一批工具调用会被
   LangGraph 用 `asyncio.gather` 并发执行，分两步做会丢掉并发线程新登记的草稿。
2. **发布必须放在 `finally` 而不是 `try` 之后**。Agent 中途报错时工具可能已经写入了 YAML，
   这些条目同样需要复核，不能因为异常就丢掉卡片。
3. **`session_id` / `turn_id` / `_current_mm` 缺任一项都必须丢弃草稿而非注册**。前端靠
   `turn_id` 定位卡片，空 `turn_id` 永远匹配不到轮次，注册只会留下拿不到的孤儿条目。

`resolve()` 是幂等的：重复决定回放**首次决定**的终态，使刷新后的陈旧卡片点一下即可自愈到
真实状态。`review_id` 不存在（服务重启、容量淘汰）时返回 `expired`，**绝不静默忽略** ——
否则前端卡片会永远停在「待处理」。

### 1. 记忆的 CRUD 存储

`BaseMemoryManager` 是抽象接口，定义 `_load_all()` / `_save_all()` / `_write_lock()` 三个原语，并在其上实现 `add()`、`delete()`、`update()`、`merge()`、`hit()` 等 CRUD 方法，以及 `show()`、`get_memories_grouped()`、`_validate_all_items()`、`show_description_history()` 等通用方法。`YamlMemoryManager` 是 YAML 后端的实现，仅需实现三个原语即可免费继承所有 CRUD 和校验逻辑，使用 `portalocker` 文件锁保证多进程并发安全。

构造方式通过 `MemoryManagerBuilder` 统一：

```python
mm = MemoryManagerBuilder() \
    .with_backend(YamlMemoryManager) \
    .with_args(yaml_file="config/personas/memory_v6.yaml") \
    .build()
```

### 2. LLM 驱动的记忆叙事与总结

`LongTermMemory` 是异步管线：每轮对话消息 → `asyncio.Queue` → 后台 LLM CRUD Agent → `memory_v6.yaml` 写入。实现了冷启动（首次无记忆）和增量更新（已有记忆）两种叙事策略。V6 起 theme 为固定九大语义主题枚举（见 `api/memory/theme.py`），单值、写入强制校验。

应用通过 `set_current_mm()` 将管理器注入为模块级全局变量供 `@tool` 函数使用：

```python
ltm = LongTermMemory(MemoryManagerBuilder().with_backend(...).build())
ltm.start()    # 内部调用 set_current_mm(self._mm) 注入管理器
```

### 3. 首次运行环境初始化

`user_init.py` 在应用启动时调用 `ensure_all()`，确保 USER.md、SOUL.md、.env 等必要文件存在，不存在时从 `.example` 模板复制。

## 关键代码片段

### 继承体系

```
BaseMemoryManager (抽象基类)
├── _load_all()            ← 抽象原语
├── _save_all()            ← 抽象原语
├── _write_lock()          ← 抽象原语（锁上下文）
├── _generate_id()         ← 默认实现：secrets.token_hex(4)
├── add / delete / update / merge / hit  ← 基于三个原语的完整 CRUD
├── _validate_all_items()  ← 字段完整性校验（介质无关）
├── show()                 ← 遍历 _load_all → [{id, description, theme}]
├── show_description_history()  ← 查找 → MemoryItem.show_description_history()
├── get_memories_grouped()      ← 分组 + 排序
│
└── YamlMemoryManager (YAML 后端)
    ├── _load_all()        ← yaml.safe_load
    ├── _save_all()        ← yaml.dump
    ├── _write_lock()      ← portalocker.Lock 上下文
    └── self_check()       ← 文件存在性 + YAML 解析 + _validate_all_items()

Data Model: MemoryItem (在 base.py 中定义)
```

### BaseMemoryManager 泛化 CRUD + _write_lock 原语

CRUD 方法在基类中基于三个原语实现，任何后端仅需覆写原语即可免费继承：

```python
# api/memory/manager/base.py

class BaseMemoryManager(ABC):

    # ── 三个抽象原语（子类必须实现） ──
    @abstractmethod
    def _load_all(self) -> dict[str, MemoryItem]: ...
    @abstractmethod
    def _save_all(self, items: dict[str, MemoryItem]) -> None: ...
    @abstractmethod
    def _write_lock(self) -> AbstractContextManager[None]: ...

    # ── 泛化 CRUD（基于原语，子类无偿继承） ──
    def add(self, description: str, theme: str) -> str:
        with self._write_lock():
            items = self._load_all()
            new_id = self._generate_id()
            items[new_id] = MemoryItem(description, theme)
            self._save_all(items)
        return new_id

    def delete(self, id: str) -> str:
        with self._write_lock():
            items = self._load_all()
            if id not in items:
                raise ValueError(f"Memory item with ID {id} not found")
            removed = items.pop(id)
            self._save_all(items)
        return removed.description

    def update(self, id: str, reason: str,
               new_description: str | None = None,
               new_theme: str | None = None) -> None:
        with self._write_lock():
            items = self._load_all()
            if id not in items:
                raise ValueError(f"Memory item with ID {id} not found")
            items[id].update(reason, new_description, new_theme)
            self._save_all(items)

    def merge(self, id1: str, id2: str,
              merged_description: str, merged_theme: str, reason: str) -> None:
        with self._write_lock():
            items = self._load_all()
            if id1 not in items or id2 not in items:
                raise ValueError(...)
            items[id1].merge(items[id2], reason, merged_description, merged_theme)
            items.pop(id2)
            self._save_all(items)

    def hit(self, id: str) -> int:
        with self._write_lock():
            items = self._load_all()
            if id not in items:
                raise ValueError(f"Memory item with ID {id} not found")
            items[id].hit += 1
            self._save_all(items)
            return items[id].hit
```

### YamlMemoryManager 仅需三个原语

```python
# api/memory/manager/yaml.py

class YamlMemoryManager(BaseMemoryManager):
    def __init__(self, yaml_file: str) -> None:
        self._yaml_file = yaml_file
        self._ensure_file_exists()

    def _load_all(self) -> dict[str, MemoryItem]:
        with yaml_path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return {id: MemoryItem(**data[id]) for id in data}

    def _save_all(self, items: dict[str, MemoryItem]) -> None:
        data_dict = {id: item.__dict__ for id, item in items.items()}
        with yaml_path.open("w", encoding="utf-8") as f:
            yaml.dump(data_dict, f, default_flow_style=False, allow_unicode=True)

    @contextmanager
    def _write_lock(self) -> None:
        with portalocker.Lock(self._lock_path, timeout=5):
            yield
```

文件锁机制：
- 使用 `portalocker.Lock` 对 `.lock` 文件加互斥锁，超时时间 5 秒
- 所有读写操作均在锁保护范围内执行
- 支持多进程/多线程并发安全

### 模块级 @tool 定义

```python
# api/memory/consumer.py

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

这些 `@tool` 函数通过模块级全局变量 `_current_mm` 委托给 `BaseMemoryManager` 实例，由 `LongTermMemory.start()` 在启动时通过 `set_current_mm()` 注入。

### 管理器注入

`LongTermMemory.start()` 在启动时通过 `set_current_mm()` 将管理器实例注入为 `consumer.py` 模块级全局变量，供六个 `@tool` 函数共用：

```
LongTermMemory.start()
  └── set_current_mm(self._mm)  → 给 consumer.py 模块级 @tool
```

## 设计要点

### 文件锁保证并发安全

所有写操作（add / delete / update / merge / hit）都通过 `_write_lock()` 保护。YAML 后端以 `portalocker.Lock` 实现该原语；数据库后端可替换为事务或行级锁等。读操作（show / show_description_history / get_memories_grouped）基于 `_load_all()` 实现，默认无锁。锁文件 (`.lock`) 与数据文件 (.yaml) 同路径，超时 5 秒。

```python
@property
def _lock_path(self) -> str:
    return self._yaml_file + ".lock"
```

### YAML 持久化

- 数据以 `dict[id → MemoryItem.__dict__]` 的格式写入 YAML
- `_load_all` / `_save_all` / `_write_lock` 是对后端的唯三抽象原语，CRUD 基于此在基类泛化实现
- ID 生成：`secrets.token_hex(4)` → 8 字符十六进制（旧版 UUID 格式由迁移脚本 `scripts/migrations/uuid-to-hex-id.py` 一次性转换）
- `MemoryItem` 在 `base.py` 中定义，提供 `show_description_history()` 历史追溯
- `_validate_all_items()` 在基类提供介质无关的字段完整性校验，`self_check` 可直接调用

### 后台总结不阻塞聊天

`LongTermMemory` 采用**生产者-消费者**异步管线：

```
send_history(user_msg)           — 生产者，非阻塞放入队列
    │
    ▼
Queue[ (session_id, turn_id, messages), ... ]
    │
    ▼
_consumer_loop()                 — 后台协程，逐条消费
    │
    ├── set_current_mm(mm)      — 兜底注入（主注入已在 start() 完成）
    ├── create_agent(llm, tools) — 创建 CRUD Agent
    ├── agent.ainvoke(...)       — LLM 调用
    ├── callback.py              — 推送 tool 事件到前端
    └── memory_v6.yaml           — 持久化写入
```

- 聊天响应直接返回用户，不等待记忆总结完成
- 后台消费者的 LLM 调用复用同一个 Provider 提供的 `BaseChatModel`
- 支持 `stop()` 安全关闭（`None` 哨兵）

## 分层边界

### 对外暴露方式

| 使用方 | 接口方式 | 具体入口 |
|--------|----------|----------|
| Agent 编排层（consumer.py） | `@tool` 函数 | `create_memory` / `read_memories` / `update_memory` / `delete_memory` / `merge_memories` / `hit_memory` |
| REST 路由层 | `LongTermMemory._mm` 方法 | `/api/long-term`、`/api/memories`、`/api/moment` |
| Vignette 前端 | REST API | `/api/memories` 端点返回分组记忆（`get_memories_grouped`） |
| Agent 工具层 | `get_narrative()` | 读取完整记忆叙事文本，作为系统提示前缀 |
| Agent 工具层 | `memory_search` 工具 → `search.py` | 主题 + 正则精确检索，沿 `related` 补齐多级关联 |

### 依赖关系

| 依赖方向 | 目标模块 | 说明 |
|----------|----------|------|
| `long_term.py →` | `manager/` | BaseMemoryManager + YamlMemoryManager + Builder |
| `long_term.py →` | `callback.py` | MemoryToolCallback |
| `long_term.py →` | `api.session.manager` | SessionState（`session.get_messages()` 提取消息） |
| `long_term.py →` | `api.session.manager` | session_manager（通过 `session_manager.get(sid).ws` 获取 WebSocket） |
| `long_term.py →` | `consumer.py` | MemoryConsumer + set_current_mm |
| `tools/system/tool_memory_search.py →` | `search.py` | 记忆精确搜索（`collect_adjacency` / `search_with_closure`） |
| `callback.py →` | `api.session.manager` | session_manager（通过 `session_manager.get(sid).ws` 获取 WebSocket） |
| `short_term.py →` | `langgraph.checkpoint.memory` | MemorySaver 全局单例 |
| `api.session.manager →` | `short_term.py` | `get_checkpointer()` / `delete_thread()` — 会话层倒依赖短期记忆模块 |
| `long_term.py →` | `api.providers` | 通过 `create_agent` 间接调用（LLM 由外部注入） |

### 设计约定评估

**已知问题**：

1. **模块级全局变量**：`consumer.py` 中的 `_current_mm` 是模块级可变全局状态，通过 `set_current_mm()` 注入。`start()` 在启动时设置一次，`_consumer_loop` 中每次迭代兜底再设一次。单消费者场景下工作正常，但若并发存在多个 `LongTermMemory` 实例（如多租户），全局状态会互相覆盖。建议改为实例级别的依赖注入，使 `@tool` 函数与具体的 `BaseMemoryManager` 实例绑定。

2. **Session 依赖方向**：`long_term.py` 和 `callback.py` 都通过 `api.session.manager.session_manager` 访问会话状态。`api.session.manager` 也反向依赖 `memory/short_term.py` 获取全局 checkpointer。这属于同一层级（第⑥层）内的模块间依赖，不违反分层规则。但应注意：`session/` 与 `memory/` 同层，彼此引入时需要避免循环依赖（当前 `short_term.py` 不依赖 `session/`，所以无风险）。

3. **模块级 @tool 的测试性**：`@tool` 函数是模块级函数而非类方法，无法在单元测试中轻松替换 `_current_mm`。模块级 `get_narrative()`（带 `lru_cache`）仍硬编码 `MEMORY_PATH` 作为回退路径。

**改进建议**：
- 将 `@tool` 函数改为类方法或工厂函数，通过闭包绑定 `BaseMemoryManager` 实例，消除全局可变状态。
- 或者使用 `contextvars` 为每个异步任务独立管理 `_current_mm`，支持多实例并发。