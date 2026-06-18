# SonettoHere 本地文件读写安全机制

## 概述

SonettoHere 采用**两层互补**的安全机制保护本地文件系统，防止 LLM 生成的代码或工具调用越权读写文件：

| 层级 | 机制 | 类型 | 粒度 | 定义方式 |
|------|------|------|------|----------|
| 第一层 | **SonettoBlocker** | 黑名单式阻断 | 目录级 | 在目标目录放置标记文件 |
| 第二层 | **路径白名单** | 白名单式允许 | 路径前缀 | YAML 配置文件 |

两条防线分别覆盖两类工具入口：

- **文件工具系列**（`file_ops`、`file_edit`、`pdf_reader`、`doc_reader`）—— 在工具入口处**显式调用**两层检查
- **exec 工具系列**（`run_python`、`debugger`）—— 通过**运行时拦截 `open()`** 隐式检查

此外，`unit_test_runner`、`syntax_checker`、`code_quality_analyzer` 等开发工具也在其 `file_path` 参数入口处执行路径白名单检查。

---

## 第一层：SonettoBlocker（黑名单阻断）

### 原理

SonettoBlocker 是一种基于**目录标记文件**的阻断机制。当某目录（或其任意级父目录）中存在文件名为 `SonettoBlocker`（不区分大小写，不限制扩展名）的文件时，该目录及其所有子目录下的文件操作都会被拒绝。

这种方式允许用户在**不修改代码**的前提下，通过简单的"放置一个文件"来标记敏感目录。

### 实现

核心函数 `check_sonetto_blocker()` 定义在 `tools/base.py:88`：

```python
def check_sonetto_blocker(target_path: str) -> str | None:
```

**检查逻辑**：

1. 将 `target_path` 解析为绝对路径（`os.path.abspath()`）
2. 从**盘符根目录**开始，逐级向下检查每一层目录
3. 每层目录中遍历所有条目，匹配忽略大小写和扩展名的 `SonettoBlocker` 文件名
4. 一旦发现标记文件，**立即返回**该目录路径（阻断）
5. 全部检查通过 → 返回 `None`（允许）

> 为什么从根向下？因为用户可能在项目根目录放置 `SonettoBlocker`，这应该拦截整个项目范围内的文件访问。

### 应用场景

- 用户在某些敏感目录（如包含密钥/配置的目录）中放置 `SonettoBlocker` 文件，防止 LLM 意外读取
- 根阻断：在项目根目录放置此文件，可彻底禁止 LLM 访问本地文件

---

## 第二层：路径白名单（白名单允许）

### 原理

路径白名单定义了一组**允许访问的路径前缀**。只有当目标路径精确等于某个前缀，或以"前缀 + 系统路径分隔符"开头时，才允许访问。

白名单文件保存在 `api/data/path_whitelist.yaml`，此文件加入 `.gitignore` 不提交。

### 自动生成

`_ensure_whitelist()` 在模块加载时自动调用一次：

| 场景 | 行为 |
|------|------|
| 文件不存在（首次启动 / git clone 后） | 自动创建，写入 `{project_root}/anthropic_skills` |
| 工程被移动（自动条目路径不匹配） | 替换自动条目路径，**保留用户添加的额外条目** |
| 文件已存在且自动条目匹配 | 不做任何操作 |
| 文件损坏或格式异常 | 全量重写（fail-secure） |

默认白名单仅包含 `anthropic_skills` 目录，遵循最小权限原则。

### 实现

核心函数 `check_path_whitelisted()` 定义在 `tools/base.py:256`：

```python
def check_path_whitelisted(target_path: str) -> str | None:
```

**检查逻辑**：

1. 目标路径正规化：`os.path.normpath(os.path.abspath(target_path))`，消除 `../` 等相对路径绕过
2. 加载 YAML 白名单 → 所有路径前缀全部正规化为绝对路径
3. 遍历比对：精确匹配 **或** 以 `allowed_prefix + os.sep` 开头 → 允许
4. **无一匹配** → 返回阻断描述字符串

> 使用 `startswith(allowed_prefix + os.sep)` 而非简单的 `startswith(allowed_prefix)`，防止 `/home/project` 误匹配 `/home/project-evil`（前缀碰撞攻击）。

### Fail-secure

- 白名单文件不存在、格式损坏、解析失败 → `_load_path_whitelist()` 返回空列表
- 空列表 → `check_path_whitelisted()` 对所有路径返回阻断
- 白名单为空时阻断消息明确提示："白名单为空或未配置"

---

## 运行时 open() 拦截

### 动机

`run_python` 和 `debugger` 通过 `exec()` 执行 LLM 生成的代码，这类代码的路径访问在**编译时无法预测**，因此需要运行时实时拦截。

### 实现

`_whitelisted_open()` — `open()` 的完整包装（`tools/base.py:288`）：

```python
def _whitelisted_open(file, mode="r", buffering=-1, encoding=None, ...):
```

与原版 `open()` 完全兼容，保留全部参数签名。检查流程：

1. 仅对字符串路径检查（跳过 `int` 类型文件描述符）
2. **先检 SonettoBlocker** → 阻断则抛 `PermissionError`（Blocker 优先）
3. **再检路径白名单** → 未通过则抛 `PermissionError`
4. 全部通过 → 调用真正的 `open()`

`get_safe_builtins()` 构造 exec 环境时替换 `open`：

```python
def get_safe_builtins() -> dict:
    safe = dict(__builtins__)  # 保留全部内置函数
    safe["open"] = _whitelisted_open  # 仅替换 open
    safe["__builtins__"] = safe
    return safe
```

所有其他内置函数（`__import__`、`eval`、`getattr` 等）保持不变，确保 LLM 代码正常使用 Python 语法特性。

---

## 两层协作策略与优先级

### 优先级规则

**SonettoBlocker 永远优先于路径白名单**。具体体现在：

1. **所有入口先检查 Blocker** → 阻断则立即返回，不继续检查白名单
2. **Blocker 通过后再检查白名单**
3. 当路径同时触发 Blocker 且不在白名单中时，**只返回 Blocker 的错误信息**

### 实现方式

**exec 工具**（`_whitelisted_open` 中）：

```python
# 1. Blocker 优先
blocked = check_sonetto_blocker(file_str)
if blocked:
    raise PermissionError("🚫 安全阻断：操作已被 SonettoBlocker 阻断。...")

# 2. 白名单次之
blocked = check_path_whitelisted(file_str)
if blocked:
    raise PermissionError(blocked)
```

**文件工具**：

```python
# 1. Blocker 优先
blocked = check_sonetto_blocker(file_path)
if blocked:
    return format_error("🚫 安全阻断：操作已被 SonettoBlocker 阻断。...")

# 2. 白名单次之
blocked = check_path_whitelisted(file_path)
if blocked:
    return format_error(blocked)
```

这个优先级确保用户可以**一票否决**：即使路径在白名单内，只要放置了 `SonettoBlocker` 文件就立即阻断。

---

## 覆盖矩阵

### 文件工具系列（显式调用两层检查）

| 工具 | 文件 | Blocker | 白名单 | 检查对象 |
|------|------|---------|--------|---------|
| `file_operations` | `tools/files/tool_file_ops.py` | ✅ 分支检查 | ✅ 分支检查 | read/write/delete 检 `file_path`，rename 检 src+dst，create/list 检 `directory_path`，search 检 `search_directory` |
| `file_edit` | `tools/files/tool_file_edit.py` | ✅ | ✅ | `file_path` |
| `pdf_reader` | `tools/files/tool_pdf_reader.py` | ✅ | ✅ | `file_path` |
| `doc_reader` | `tools/files/tool_doc_reader.py` | ✅ | ✅ | `file_path` |

### exec 工具系列（运行时拦截 open()）

| 工具 | 文件 | Blocker | 白名单 | 检查方式 |
|------|------|---------|--------|---------|
| `run_python` | `tools/system/tool_python.py` | ✅ 通过 `_whitelisted_open` | ✅ 通过 `_whitelisted_open` | `exec(code, {"__builtins__": _SAFE_BUILTINS})` |
| `debugger` | `tools/development/tool_debug.py` | ✅ 通过 `_whitelisted_open` | ✅ 通过 `_whitelisted_open` | `exec(code, {"__builtins__": get_safe_builtins()}, env)` |

### 开发工具系列（仅显式白名单检查）

| 工具 | 文件 | Blocker | 白名单 | 检查对象 |
|------|------|---------|--------|---------|
| `unit_test_runner` | `tools/development/tool_unit_test.py` | ❌ | ✅ | `test_file` |
| `syntax_checker` | `tools/development/tool_syntax.py` | ❌ | ✅ | `file_path` |
| `code_quality_analyzer` | `tools/development/tool_code_quality.py` | ❌ | ✅ | `file_path` |

> 开发工具系列没有运行时 exec()，所有路径都通过参数显式传入，因此只需在入口处检查白名单。

---

## 工具安全调用示例

### 文件工具（以 `file_edit.py` 为例）

```python
# 1. Blocker 检查
blocked = check_sonetto_blocker(file_path)
if blocked:
    return format_error("🚫 安全阻断：操作已被 SonettoBlocker 阻断。\n"
                        f"在目录 \"{blocked}\" 中发现了 SonettoBlocker 文件。\n"
                        "请立即停止当前任务，先说明你为什么需要访问该路径，"
                        "再说明下一步打算做什么。")

# 2. 白名单检查
blocked = check_path_whitelisted(file_path)
if blocked:
    return format_error(blocked)
```

### exec 工具（`run_python`）

```python
_SAFE_BUILTINS = get_safe_builtins()  # 模块级，只构造一次

def _exec_code(code: str) -> str:
    exec(code, {"__builtins__": _SAFE_BUILTINS})
    # 代码内的 open() 实际调用 _whitelisted_open
```

### 复杂操作的分支检查（`file_ops.py`）

`rename_file` 操作需要同时检查源和目标路径：

```python
# Blocker（优先）
if operation == "rename_file":
    for p in (file_path, new_path):
        if p:
            blocked = check_sonetto_blocker(p)
            if blocked:
                blocker_paths.append(blocked)

# 白名单（次之，仅当 Blocker 未阻断时）
if whitelist_checks_needed:
    for p in (file_path, new_path):
        if p:
            blocked = check_path_whitelisted(p)
            if blocked:
                whitelist_blocked.append(p)
```

---

## 安全边界与局限

### 防护范围 ✅

| 攻击向量 | 防护状态 | 说明 |
|----------|----------|------|
| 直接 `open()` | ✅ 受控 | `_whitelisted_open` 拦截所有 `open()` 调用 |
| 相对路径遍历（`../../etc`） | ✅ 受控 | `abspath()` + `normpath()` 正规化后检查 |
| 前缀碰撞（`/proj-evil`） | ✅ 受控 | `startswith(prefix + os.sep)` 精准匹配 |
| 文件描述符绕过 | ✅ 受控 | `int` 类型 file 参数跳过检查（此类调用仅来自内部代码） |
| Blocker 标记文件 | ✅ 受控 | 从根逐级检查所有父目录 |

### 已知局限 ⚠️

| 局限 | 原因 | 影响评估 |
|------|------|----------|
| `os.open()` / `os.system()` / `subprocess` 不受控 | 只替换了 `open`，未替换 `os` / `subprocess` 模块 | 中等 — LLM 可通过这些 API 绕过白名单 |
| 类层级遍历可找回原始 `open` | `().__class__.__bases__[0].__subclasses__()` 可绕过一切 Python exec 沙箱 | 低 — 需要刻意对抗，日常不会发生 |
| `PermissionError` 可被 `try/except` 捕获 | exec 代码可捕获异常，阻塞被感知但不影响阻断效果 | 低 — 文件仍然不会被打开 |
| 白名单文件本身未受保护 | 用户可以直接编辑 `path_whitelist.yaml` | 低 — 文件在用户本地，信任用户 |
| 开发工具无 Blocker 检查 | `unit_test_runner` 等工具只有白名单检查 | 低 — 这些工具只接受文件路径参数，不走 exec |

### 不在此设计范围内的威胁

- **任意代码执行防护**：`exec()` 本身就可以执行任意 Python 代码，防护它的所有攻击面是沙箱工程，不在本机制范围内
- **模块导入劫持**：`__import__` 保持原生状态，不做模块级路径过滤
- **对外网络请求**：文件安全机制不涉及网络层防护

---

## 数据流全景

```
LLM / Agent
  │
  ├── 调用文件工具 ───────────────────────┐
  │     │                                │
  │     ▼                                │
  │   file_path / directory_path         │
  │     │                                │
  │     ▼                                │
  │   check_sonetto_blocker(path)        │
  │     │  ┌─ 找到 SonettoBlocker? ──►   │
  │     │  │  返回阻断消息 (Blocker 优先)  │
  │     │  └─ 未找到 ─────────────────►   │
  │     ▼                                │
  │   check_path_whitelisted(path)       │
  │     │  ┌─ 在白名单内? ────────────►   │
  │     │  │  → 执行操作                  │
  │     │  └─ 不在白名单内 ───────────►   │
  │     │    返回阻断消息                  │
  │                                      │
  ├── 调用 exec 工具 ─────────────────────┐
  │     │                                │
  │     ▼                                │
  │   exec(code, {"__builtins__": ...})  │
  │     │                                │
  │     ▼  (代码内调用 open())            │
  │   _whitelisted_open(path)            │
  │     │                                │
  │     ▼                                │
  │   check_sonetto_blocker(path)        │
  │     │  ┌─ 阻断? ──► PermissionError   │
  │     │  └─ 通过 ──►                   │
  │     ▼                                │
  │   check_path_whitelisted(path)       │
  │     │  ┌─ 阻断? ──► PermissionError   │
  │     │  └─ 通过 ──► 真正 open()        │
  │                                      │
  └── 调用开发工具 ───────────────────────┐
        │                                │
        ▼                                │
     check_path_whitelisted(test_file)   │
        │  ┌─ 阻断? ──► 返回错误           │
        │  └─ 通过 ──► 执行分析            │
```

---

## 配置与使用

### 添加白名单路径

编辑 `api/data/path_whitelist.yaml`：

```yaml
whitelist:
  - path: "D:/data"
    description: 用户数据目录
  - path: "/mnt/share"
    description: 网络共享目录
```

### 添加 Blocker 阻断

在要拦截的目录中创建任意文件，文件名忽略大小写为 `SonettoBlocker`（可带任意扩展名）：

```bash
# 阻断整个文档目录
echo "DO NOT READ" > ~/Documents/SonettoBlocker
# 也可带扩展名
echo "" > ./secrets/SonettoBlocker.txt
```

### 移除阻断

删除对应目录下的 `SonettoBlocker` 文件即可：

```bash
rm ~/Documents/SonettoBlocker
```

---

## 变更历史

| 日期 | 变更 | 作者 |
|------|------|------|
| 2026-06-18 | 初始编写：完整记录两层安全体系 | Claude Code |
| 2026-06-18 | 补充覆盖矩阵和数据流全景 | Claude Code |
