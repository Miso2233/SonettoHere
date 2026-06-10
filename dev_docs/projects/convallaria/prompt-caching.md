# 铃兰计划 — Prompt Caching 前缀优化

## 概述

铃兰计划（Project Convallaria）旨在最大化 Anthropic Prompt Caching 的缓存命中率。核心策略：**确保每次 API 调用发送的系统提示词前缀字节级一致，且尽可能长**。

前缀越长 → 缓存节省越多，前缀越稳定 → 缓存命中率越高。

---

## 提示词构筑现状

### 系统提示词最终形态

```
## 行为规则
{AGENTS.md}

## 性格设定
{SOUL.md}

## 用户自述
{USER.md}

## 我对用户的记忆
{memory.yaml 格式化叙事}

## 可用 Anthropic Skills
{anthropic_skills/ 下各 SKILL.md 元数据清单}
```

### 调用路径

```python
# api/routes/chat.py:213 — 每次对话轮次都重新组装
system_prompt = build_system_prompt()

# skills/sub_agent/skill_call_sub_agent.py:146 — 子 Agent 同样重新组装
system_prompt = build_system_prompt()

# api/dependencies.py:42 — 惰性单例（但上述两处绕过此缓存）
_system_prompt = build_system_prompt()
```

### 各组件缓存状态一览

| 组件 | 缓存 | 磁盘 I/O | 变更风险 |
|------|------|----------|----------|
| `AGENTS.md` | `@lru_cache(maxsize=3)` ✅ | 仅首次 | 极低（代码库静态文件） |
| `SOUL.md` | 同上（共享同一缓存） ✅ | 仅首次 | 极低 |
| `USER.md` | 无 ❌（**本次已修复**） | 每次 | 低（用户自述，极少修改） |
| `get_narrative()` | `@lru_cache(maxsize=1)` ✅（**本次新增**） | 仅首次 | 低（后台 Agent 可能更新） |
| `_scan_anthropic_skills()` | 无 ❌（**本次已修复**） | 每次扫描目录 | 低（静态 skill 文件） |
| `build_system_prompt()` 本身 | `@lru_cache(maxsize=1)` ✅（**本次新增**） | 仅首次 | — |

---

## 已实施优化

### 1. 缓存 `get_narrative()` — 记忆叙事进程级驻留

**文件：** `memory/narrative.py:114`

```python
@lru_cache(maxsize=1)
def get_narrative() -> str:
```

- 效果：`memory.yaml` 在进程生命周期内只读取并解析一次
- 避免：后台 Agent 更新 memory.yaml 后，系统提示词重建时前缀漂移

### 2. 移除系统提示词中的当前时间

**文件：** `agent/prompts.py:77（已删除）`

```diff
- now = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
- ...
- f"当前时间：{now}",
```

- 效果：消除每次进程重启时提示词前缀的最大漂移源
- 背景：时间戳每秒变更，即使 5 分钟 TTL 窗口内也几乎不可能命中缓存

### 3. 缓存 `build_system_prompt()` 本身

**文件：** `agent/prompts.py:73`

```python
@lru_cache(maxsize=1)
def build_system_prompt() -> str:
```

- 效果：**一劳永逸**。首次调用后所有子组件（含 USER.md 的读取、anthropic_skills 的目录扫描）均不再执行
- 子 Agent 调用 `build_system_prompt()` 时同样命中缓存，无需单独优化

### 4. 前端消息元数据结构化改造

**涉及文件：** `types/index.ts`、`references.ts`、`ChatInput.vue`、`useChat.ts`、`MessageBubble.vue`、`ChatWindow.vue`、`ChatView.vue`

- `ChatTurn.userMessage` 改为纯文本，不再嵌入时间尾缀和引用元数据
- `ChatTurn.refs` 以 `ParsedRef[]` 结构化存储
- 时间尾缀只在 `useChat.send()` 序列化边界构造并嵌入 WebSocket 消息，前端不存储不解析
- `MessageBubble.vue` 不再需要 `parseReferences()` 和正则剥离时间，直接消费纯文本 + 结构化 refs
- **与系统提示词前缀无直接关系**，但消除了前端渲染侧的字符串解析开销

### 5. `list_memories` / `read_memories` 拆分

**涉及文件：** `skills/memory/skill_list_memories.py`（新建）、`skill_read_memories.py`（重写）、`__init__.py`、`SKILL.md`、`tool_extractors.py`

- `list_memories`：列出所有记忆条目概览，每条 description 截断至 200 字
- `read_memories <id>`：按 ID 读取单条记忆的完整内容（含变更历史）
- 截断后的列表中每条记忆节省约 40% 上下文，整体提示词更紧凑

---

## 缓存命中确保策略

### 进程生命周期

```
进程启动 → build_system_prompt() 首次调用
           ├─ ensure_user_md()          ← 写入默认 USER.md（如不存在）
           ├─ _read_persona("AGENTS.md") ← @lru_cache 首次，写缓存
           ├─ _read_persona("SOUL.md")   ← @lru_cache 首次，写缓存
           ├─ _read_if_exists("USER.md") ← 磁盘读取（首次）
           ├─ get_narrative()            ← @lru_cache 首次，写缓存
           └─ _scan_anthropic_skills()   ← 目录扫描 + 文件读取（首次）
                ↓
           返回字符串，@lru_cache 缓存
                ↓
进程运行期内所有对话轮次 → build_system_prompt() 返回缓存结果（零磁盘 I/O）
                ↓
进程重启 → 缓存清空 → 重新组装（memory.yaml 最新内容进入提示词）
```

### 关键设计决策

- **进程级缓存**：前缀在进程运行期内完全不变。进程重启后自然刷新（memory.yaml 的最新记忆、USER.md 的修改等）
- **不追求跨进程缓存**：不同进程实例的前缀因 memory.yaml 内容不同天然不一致，跨进程缓存命中率提升有限，不值得为跨进程持久化增加复杂度
- **子 Agent 共享缓存**：子 Agent 调用 `build_system_prompt()` 直接命中进程级 LRU 缓存，前缀与主 Agent 完全一致

---

## 验证方法

### 1. 前缀一致性验证

在任意两轮对话中分别打印 `system_prompt[:500]`，确认完全一致：

```python
# 在 chat.py 的 _run_agent_turn 中添加
a = build_system_prompt()
b = build_system_prompt()
assert a == b, "系统提示词不一致！"
assert a is b, "系统提示词不是同一对象！"
```

### 2. 磁盘 I/O 验证

使用 `strace` 或 `audit` 跟踪文件访问：

```bash
# Linux / WSL
strace -e trace=openat,read -p $(pgrep -f uvicorn) 2>&1 | grep -E "memory\.yaml|USER\.md" | head -20
```

首次调用后，memory.yaml 和 USER.md 不应再次被打开。

### 3. 缓存命中率监控

通过 Anthropic API 响应头 `x- Anthropic-Token-Count-By-Type` 查看：

```json
{
  "cache_creation_input_tokens": 2000,   // 首次创建缓存
  "cache_read_input_tokens": 1800         // 后续命中缓存
}
```

---

## 维护原则

### 不要破坏前缀稳定性的操作

- ❌ 在 `build_system_prompt()` 中插入时间戳、随机数、计数器等变化值
- ❌ 在提示词中嵌入 `datetime.now()`、`uuid4()` 等运行时生成的值
- ❌ 在 `build_system_prompt()` 内读取可能在运行时变更的文件（应使用 LRU 缓存）

### 鼓励的操作

- ✅ 将静态配置/人格文件（AGENTS.md、SOUL.md）保持在提示词组装路径中
- ✅ 将大段静态文本（行为规则、性格设定）放在提示词**前面**（前缀越长缓存收益越大）
- ✅ 新增组件时使用 `@lru_cache` 装饰无参或参数稳定的函数
- ✅ 运行时变化的元数据（如时间、会话 ID）通过**用户消息**或 **tool 返回值**注入，而非嵌入系统提示词前缀

### 新增提示词组件的检查清单

```markdown
- [ ] 组件输出在进程生命周期内是否确定不变？
- [ ] 如否，是否可 LRU 缓存？
- [ ] 如否，是否应移至用户消息而非系统提示词？
- [ ] 是否在提示词前部（增加前缀长度）？
```
