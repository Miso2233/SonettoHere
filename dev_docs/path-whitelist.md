# 路径白名单审查机制

## 背景

SonettoHere 的 Python 执行工具（`run_python`、`debugger`）通过 `exec()` 执行 LLM 生成的代码时，原先暴露了完整的 Python 内置函数，被执行代码可以自由读写系统中任何路径的文件。同时 `unit_test_runner`、`syntax_checker`、`code_quality_analyzer` 等工具接受文件路径参数却未做任何验证。

此前仅有文件操作工具通过 `check_sonetto_blocker()` 实现了基本的阻断机制（检查目录中是否存在 `SonettoBlocker` 标记文件），但缺少一个"白名单允许"机制——即只有明确授权的路径才能被访问。

## 设计目标

1. **简单** —— 白名单定义在一个本地 YAML 文件中，无需数据库或 UI
2. **零配置启动** —— 首次运行自动创建，根据当前工程目录自动填入项目根目录
3. **不提交 git** —— 白名单文件在 `.gitignore` 中，每用户本地独立配置
4. **工程移动自适应** —— 工程目录变更后自动替换项目根路径，用户自定义条目保留
5. **安全默认** —— 默认只允许项目根目录，白名单缺失时全阻断（fail-secure）
6. **低侵入** —— 不依赖第三方沙箱库，不改动项目框架
7. **日常友好** —— 不影响 LLM 正常使用 `import`、`eval` 等语法特性

## 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                    LLM / Agent                           │
└──────────┬──────────────────────┬───────────────────────┘
           │                      │
           ▼                      ▼
┌──────────────────┐   ┌──────────────────────────┐
│  工具参数路径     │   │  exec() 内 open() 调用    │
│  (test_file/     │   │  (run_python / debugger)  │
│   file_path)     │   │                          │
└────────┬─────────┘   └───────────┬──────────────┘
         │                         │
         ▼                         ▼
┌────────────────────────────────────────────────────────┐
│              check_path_whitelisted()                   │
│   ┌────────────────────────────────────────────────┐   │
│   │  遍历白名单，检查目标是否以任一允许前缀开头      │   │
│   │  精确匹配 / 前缀+分隔符匹配，防前缀碰撞逃逸     │   │
│   └────────────────────────────────────────────────┘   │
└──────────────────────┬─────────────────────────────────┘
                       │
                       ▼
┌────────────────────────────────────────────────────────┐
│           api/data/path_whitelist.yaml                  │
│   ┌────────────────────────────────────────────────┐   │
│   │   启动时自动生成（_ensure_whitelist()）          │   │
│   │   - 文件缺失 → 创建，写入当前项目根目录         │   │
│   │   - 工程移动 → 替换根路径，保留用户条目         │   │
│   │   - 文件已就绪 → 不做操作                      │   │
│   └────────────────────────────────────────────────┘   │
│   whitelist:                                           │
│     - path: "{project_root}/anthropic_skills"           │
│       description: 技能目录（自动生成）                 │
└────────────────────────────────────────────────────────┘
```

## 核心实现

### 1. 白名单文件

**路径**: `api/data/path_whitelist.yaml`

该文件**不提交 git**（已在 `.gitignore` 中），首次启动时由 `_ensure_whitelist()` 自动创建：

```yaml
# 路径白名单（自动生成，首次 import 时创建）
# 编辑此文件以添加更多允许的路径前缀。
whitelist:
- description: 技能目录（自动生成）
  path: C:\Users\xxx\PycharmProjects\SonettoHere\anthropic_skills
```

- 每个条目包含 `path`（允许的路径前缀，支持正斜杠/反斜杠）和可选的 `description`
- 可添加多个条目来允许不同目录
- 白名单为空、缺失或解析失败时，所有路径都被阻断（fail-secure）

#### 自动生成行为

`_ensure_whitelist()` 在模块导入时（即应用启动时）运行一次：

| 场景 | 行为 |
|------|------|
| 文件不存在（首次启动 / git clone 后） | 自动创建，写入 `_PROJECT_ROOT/anthropic_skills` |
| 工程被移动（自动条目路径不匹配） | 替换自动条目路径，用户添加的额外条目保留 |
| 文件已存在且自动条目匹配 | 不做任何操作 |

> **为什么是 `anthropic_skills`？** 该目录存放用户自定义的技能文件，是工具执行时最常需要读写的位置。项目根目录下其余代码库（`tools/`、`api/` 等）不被默认暴露，遵循最小权限原则。

### 2. 核心函数

定义在 `tools/base.py`，与已有的 `check_sonetto_blocker()` 同级。

#### `_ensure_whitelist()`

启动时自动调用一次，确保白名单文件存在且项目根目录正确：

1. 文件不存在 → 调用 `_write_whitelist()` 创建默认文件
2. 文件存在但内容无效（损坏 / 不是列表） → 重写默认文件
3. 文件存在且有效 → 检查是否有条目匹配当前项目根目录
   - 匹配 → 不做操作
   - 不匹配 → 寻找 `description == "项目根目录（自动生成）"` 的旧条目并更新其 `path`；若无则插入新条目
4. YAML 加载异常时全量重写（fail-secure）

> 用户手动添加的额外条目（不带"自动生成"标记）在工程移动更新时会被保留。

#### `check_path_whitelisted(target_path: str) -> str | None`

路径白名单检查的统一入口：

1. 将 `target_path` 正规化为绝对路径（`os.path.normpath(os.path.abspath())`），消除 `../` 等相对路径绕过
2. 加载白名单文件中的路径前缀列表
3. 逐一比对：若目标路径**精确等于**某个前缀，或目标路径以**前缀 + `os.sep`** 开头，则允许
4. 返回 `None` = 允许；返回 `str` = 阻断原因描述

> 使用 `startswith(allowed_prefix + os.sep)` 而非简单的 `startswith(allowed_prefix)`，防止 `/home/project` 误匹配 `/home/project-evil`。

#### `_whitelisted_open(file, mode, ...) -> file object`

Python 内置 `open()` 的包装版本，`get_safe_builtins()` 在构造 exec 环境时用此函数替代原版 `open`：

1. 检查 `file` 参数是否为字符串路径（跳过已打开的文件描述符）
2. 调用 `check_path_whitelisted()` 检查该路径
3. 未通过 → 抛出 `PermissionError`
4. 通过 → 调用真正的 `open()` 执行操作

#### `get_safe_builtins() -> dict`

构造一个安全的 `__builtins__` 字典给 `exec()` 使用：

1. 复制全部内置函数（152+ 个）
2. 仅将 `open` 替换为 `_whitelisted_open`，其余所有函数（`__import__`、`eval`、`getattr` 等）保留
3. 设置 `__builtins__` 自引用，使被执行代码看到的 `__builtins__` 也是同一份安全版本

### 3. 在各工具中的应用

#### 路径参数验证（编译时检查）

在工具接受文件路径参数的入口处显式调用 `check_path_whitelisted()`：

| 工具 | 文件 | 验证的参数 |
|------|------|-----------|
| `unit_test_runner` | `tools/development/tool_unit_test.py` | `test_file` |
| `syntax_checker` | `tools/development/tool_syntax.py` | `file_path` |
| `code_quality_analyzer` | `tools/development/tool_code_quality.py` | `file_path` |

调用模式：

```python
blocked = check_path_whitelisted(test_file)
if blocked:
    return format_error(blocked)
```

#### exec() 运行时拦截（运行时检查）

`run_python` 和 `debugger` 通过 `exec()` 执行的代码无法预先知道会访问哪些路径，因此采用运行时拦截：

- `exec()` 的全局命名空间传入 `get_safe_builtins()` 返回的字典
- 被执行代码中的 `open()` 实际上是 `_whitelisted_open`，在每次打开文件时实时检查白名单
- 非白名单路径 → `PermissionError`，由 exec 的异常捕获流程返回给 LLM

### 4. 与 SonettoBlocker 的关系

现有 SonettoBlocker 和白名单是互补的两层：

| 机制 | 作用 | 范围 |
|------|------|------|
| **SonettoBlocker** | 黑名单式阻断（目录中存在标记文件即阻断） | 仅文件操作工具 |
| **路径白名单** | 白名单式允许（仅允许已列出的前缀） | Python 执行工具 + 开发工具 |

SonettoBlocker 的"阻断"层级更高——即使路径在白名单内，如果某级目录存在 `SonettoBlocker` 文件，仍然会被阻断。

## 安全边界与局限

### 防护范围

- **直接 `open()` 调用** —— ✅ 受控，白名单外路径抛 `PermissionError`
- **相对路径遍历** —— ✅ `abspath()` 解析后检查，`../../etc/passwd` 无法绕过
- **前缀碰撞** —— ✅ `startswith(prefix + os.sep)` 排除
- **文件描述符绕过** —— ✅ `_whitelisted_open` 对 `int` 类型的 `file` 参数跳过检查（此类调用由内部代码而非 LLM 生成代码发起）

### 已知局限

- **`os.open()` / `os.system()` / `subprocess` 等间接路径访问不受限** —— 因为 LLM 代码可以通过 `import os` 获得 `os.open()`，其绕过白名单。要拦截这些需要对模块本身的函数做替换，超出了"简单机制"的范围。如果后续需要加强，可以考虑替换 `__import__` 返回包装过的模块，但这会显著增加复杂度。

- **类层级遍历逃逸** —— 即使替换了 `open`，`().__class__.__bases__[0].__subclasses__()` 仍能找到原始 `open`。这是 Python `exec()` 沙箱的固有难题，不在本机制的解决范围内。

- **`PermissionError` 可被捕获** —— 被执行代码可以用 `try/except PermissionError` 捕获阻断异常，但这不影响阻断本身的效果，文件仍然不会被打开。

## 配置指南

### 添加允许路径

编辑 `api/data/path_whitelist.yaml`，添加新条目：

```yaml
whitelist:
  - path: "D:/data"
    description: 用户数据目录
  - path: "/tmp"
    description: 系统临时目录
  - path: "/mnt/share"
    description: 网络共享目录
```

> 自动生成的技能目录无需手动添加。用户只需添加额外需要访问的目录。
> 路径格式支持 Windows (`D:/xxx`) 和 POSIX (`/tmp`) 风格，`os.path.abspath()` 会做平台相关解析。

### 安全建议

- 遵循最小权限原则——只添加必要的目录
- 默认仅开放 `anthropic_skills`，不要随意放回整个项目根目录
- 对于临时文件读写，应在项目目录内创建专门的子目录并单独添加
- 生产环境不应包含 `/tmp` 等全局可写目录

## 测试

在项目根目录执行以下验证（无需启动服务）：

```bash
python -c "
import sys; sys.path.insert(0, '.')
from tools.base import check_path_whitelisted, get_safe_builtins

# 测试白名单
assert check_path_whitelisted('tools/base.py') is None           # 允许
assert check_path_whitelisted('C:/Windows/System32') is not None # 阻断

# 测试 safe builtins
rb = get_safe_builtins()
exec('import math; print(math.pi)', {'__builtins__': rb})       # 正常
exec('open(\"C:/Windows/System32/hosts\")', {'__builtins__': rb})  # PermissionError

print('All checks passed.')
"
```

## 变更历史

| 日期 | 变更 | 作者 |
|------|------|------|
| 2026-06-18 | 初始实现：路径白名单 + open 运行时拦截 + 工具参数验证 | Claude Code |
| 2026-06-18 | 白名单改为自动生成，不跟踪 git，工程移动自适应 | Claude Code |
