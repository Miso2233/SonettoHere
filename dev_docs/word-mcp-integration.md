# Office-Word-MCP-Server 集成复盘

本文档记录将 Office-Word-MCP-Server 通过 `langchain-mcp-adapters` 集成到 SonettoHere 的完整过程、遇到的问题及解决思路，作为后续 MCP 工具集成的参考范例。

---

## 一、成果

| 指标 | 数值 |
|------|------|
| 集成工具数 | 54 个 （含 `word_` 前缀） |
| 后端代码量 | ~40 行（`skills/mcp.py`） |
| 包裝脚本 | 1 个（`scripts/mcp_word_server.py`） |
| 前端气泡 | 1 个统一组件（`WordBubble.vue`） |
| 涉及客户端 | CLI / QQ Bot / Web API 三端 |

---

## 二、架构

```
Agent 进程
  └─ init_mcp_tools()                    skills/mcp.py
       └─ MultiServerMCPClient            langchain-mcp-adapters
            └─ subprocess                 sys.executable
                 └─ scripts/mcp_word_server.py    包装脚本
                      └─ word_document_server.main.run_server()
                           └─ FastMCP (stdio transport)
```

MCP Server 不作为独立服务运行，而是由 `MultiServerMCPClient` 在需要时自动衍生子进程，通过 stdio JSON-RPC 通信。主进程退出时子进程自动终止。

---

## 三、遇到的问题与解决思路

### 3.1 模块入口路径错误

**现象**：`python -m office_word_mcp_server.word_mcp_server` 报 `No module named`。

**原因**：`office_word_mcp_server` 只是一个薄包，`__init__.py` 仅从 `word_document_server.main` re-export 了 `run_server()`，本身不包含可运行的 `__main__` 模块。真正的入口在 `word_document_server.main.run_server()`。

**教训**：对于新引入的 MCP 包，不要依赖文档或直觉判断模块路径。先 `pip show` 确认安装位置，然后检查包内目录结构，找到实际包含 `mcp.run()` 或 `FastMCP(...)` 入口的文件。

```bash
# 推荐的探查流程
pip show office-word-mcp-server
# Location → site-packages/office_word_mcp_server/
ls $(python -c "import office_word_mcp_server; print(office_word_mcp_server.__file__)")
# 发现是薄包，进一步查找
ls $(dirname $(python -c "import office_word_mcp_server; print(office_word_mcp_server.__file__)"))/../word_document_server/
```

**解决**：不依赖 `-m` 方式，而是创建一个包装脚本直接 `import` + 调用。

### 3.2 Stdout 污染破坏 JSON-RPC

**现象**：MCP stdio 协议通过 stdout 传输 JSON-RPC 消息。但服务启动时各种 `print()` 语句直接写入 stdout，导致客户端收到非 JSON 数据，解析失败。

**错误日志特征**：
```
Failed to parse JSONRPC message from server
ValidationError: Invalid JSON: expected value at line 1 column 1
input_value='Loading configuration from .env file...\r'
```

**涉及的全部污染源**：
1. `print("Loading configuration from .env file...")` — dotenv 加载提示
2. `print("Transport: stdio")` — 传输方式日志
3. `print("Starting Word Document MCP Server...")` / `print("Server running on stdio transport")`
4. FastMCP 3.x 的 rich 横幅

**解决思路**：在导入服务模块前 monkey-patch `builtins.print` 将输出重定向到 stderr。MCP 框架内部使用 `sys.stdout.buffer.write()` 而非 `print()`，不受影响。

```python
# scripts/mcp_word_server.py 核心逻辑
import builtins
_original_print = builtins.print
def _stderr_print(*args, **kwargs):
    kwargs.setdefault("file", sys.stderr)
    _original_print(*args, **kwargs)
builtins.print = _stderr_print

from word_document_server.main import run_server
run_server()
```

**经验**：重定向 `print()` 通常足够，因为大部分库用 `print()` 输出日志。如果遇到直接用 `sys.stdout.write()` 的库，则需考虑更底层的重定向。FastMCP 的 rich 横幅走 stderr，恰好不受影响。

**后续 MCP 集成的标准做法**：每个有 stdout 污染风险的 MCP Server 都应创建一个包装脚本，在 import 前 patch `print`。

### 3.3 子进程 Python 解释器路径

**现象**：`MultiServerMCPClient` 配置 `"command": "python"` 时，子进程可能解析到系统 Python 而非虚拟环境 Python。

**解决**：使用 `sys.executable` 显式指定当前进程的 Python 解释器路径，保证父子进程环境一致。

```python
"command": sys.executable,   # 始终使用当前 venv 的 Python
```

### 3.4 MultiServerMCPClient 清理

**现象**：尝试 `await client.__aexit__(...)` 时抛出 `NotImplementedError`。

**原因**：`langchain-mcp-adapters` 的 `MultiServerMCPClient` 未实现异步上下文管理器协议。

**解决**：将 client 和 tools 引用设为 `None`，交由 GC 回收。子进程在主进程退出时自动终止。

```python
async def close_mcp():
    global _client, _tools
    _client = None   # 释放引用，GC 回收时终止子进程
    _tools = None
```

### 3.5 工具命名冲突

**现象**：MCP 返回的工具有 `add_paragraph`、`add_heading` 等通用名称，可能与未来新增的 Skill 重名。

**解决**：`MultiServerMCPClient` 提供 `tool_name_prefix=True` 参数，自动以 server name 做前缀（`word_add_paragraph`）。无需手动重命名。

### 3.6 54 个工具的前端注册

**现象**：Word 系列有 54 个工具，若逐个注册到气泡组件映射表会非常臃肿。

**解决**：在 `getBubbleComponent()` 中增加前缀匹配逻辑，所有 `word_*` 工具统一路由到 `WordBubble.vue`。

```typescript
export function getBubbleComponent(name: string): Component | null {
  if (registry[name]) return registry[name]
  if (name.startsWith('word_')) return WordBubble   // 前缀匹配
  return null
}
```

同样在 `toolDisplayName()` 中处理前缀兜底。

### 3.7 前端气泡内容如何丰富 — toolData 通道（承前启后）

当前的 `WordBubble.vue` 在前端解析 `toolCall.input` 的 JSON 字符串提取参数，这种方式信息量有限、且无法感知工具执行结果的结构化数据。项目已有完善的 **toolData 通道**，应优先使用。

#### toolData 全链路

```
Skill._run() 返回 dict
  → ToolMessage(content=json.dumps({"data": {...}}))
    → WebSocketCallback.on_tool_end()
      → _extract_tool_data(tool_name, output)
        → tool_extractors._dispatch(tool_name, parsed)
          → 匹配 extractor 函数 → 返回结构化 dict
            → WebSocket 发送 {"type": "tool_end", "tool_data": {...}}
              → 前端 ToolCall.toolData
                → 气泡组件从 toolCall.toolData 读取字段
```

#### 关键文件

| 文件 | 作用 |
|------|------|
| [tool_extractors.py](../api/callbacks/tool_extractors.py) | 注册 extractor 函数，将工具输出转为前端结构化数据 |
| [websocket_callback.py:95](../api/callbacks/websocket_callback.py#L95) | `_extract_tool_data()` 调用 dispatch |
| [WordBubble.vue](../web/src/components/tools/WordBubble.vue) | 前端气泡从 `toolCall.toolData` 取数渲染 |

#### 为 word_* 系列注册 extractor

在 `tool_extractors.py` 中添加前缀匹配的 extractor：

```python
@register_prefix("word_")
def _extract_word(
    tool_name: str, parsed: dict[str, Any], tool_input: str | None = None,
) -> dict[str, Any] | None:
    data = _get_data(parsed)
    if data is None:
        return None
    # 去掉 word_ 前缀取动作名
    action = tool_name.replace("word_", "")
    result: dict[str, Any] = {"action": action}
    # 提取 filename
    for key in ("filename", "source_filename", "output_filename"):
        if tool_input:
            try:
                inp = json.loads(tool_input)
                if inp.get(key):
                    result["filename"] = inp[key]
                    break
            except json.JSONDecodeError:
                pass
    # 从 data 中读取结果信息（各工具返回结构不同，按需提取）
    if "message" in data:
        result["message"] = data["message"]
    if "paragraph_count" in data:
        result["paragraph_count"] = data["paragraph_count"]
    if "table_index" in data:
        result["table_index"] = data["table_index"]
    return result
```

#### extractor 的三种数据来源

1. **`parsed`**（即 tool output 的 JSON 解析结果）— 优先来源，包含执行结果的结构化数据
2. **`tool_input`**（原始入参 JSON 字符串）— 提取文件名等入参信息
3. **`tool_name`** — 区分具体工具，做不同处理

#### 前端取用

注册 extractor 后，`WebSocketCallback` 会自动将返回值注入 `tool_end` 事件的 `tool_data` 字段。前端 `ToolCall.toolData` 自动携带这些数据，`WordBubble.vue` 中直接读取：

```typescript
const td = computed(() => props.toolCall.toolData as Record<string, any> ?? {})

// 直接使用
td.value.action      // "create_document"
td.value.filename    // "报告.docx"
td.value.message     // "文档创建成功"
```

#### 扩展建议

按工具类别细化 extractor 返回值：

| 工具类别 | extractor 应返回的字段 |
|----------|----------------------|
| 文档创建/复制 `create_document` `copy_document` | `action`, `filename`, `message` |
| 内容插入 `add_paragraph` `add_heading` `add_table` | `action`, `filename`, `content_preview`, `table_size` |
| 格式化 `format_text` `format_table` | `action`, `filename`, `changes_summary` |
| 表格操作 `merge_table_cells` `set_table_column_width` | `action`, `filename`, `table_index`, `affected_cells` |
| 脚注 `add_footnote_to_document` | `action`, `filename`, `footnote_count` |
| 查找替换 `search_and_replace` | `action`, `filename`, `replacements_count` |
| 文档保护 `protect_document` | `action`, `filename`, `protected` |
| 转换 `convert_to_pdf` | `action`, `filename`, `output_filename` |
| 查询类 `get_document_info` `get_document_text` | `action`, `filename`, `summary_stats` |

#### 注意事项

- extractor 返回 `None` 时，前端 `toolData` 为 `undefined`，气泡组件应做好防御
- 不要在前端解析 `toolCall.output` 字符串来获取结构化数据 — 那是给 LLM 看的，不是给 UI 用的
- 同一 `register_prefix("word_")` 覆盖全部 54 个工具，按 `action` 分支处理即可，无需每个工具单独注册

---

## 四、MCP 集成清单（供后续参考）

后续接入新的 MCP Server 时，按以下步骤检查：

### 4.1 探查阶段
- [ ] `pip show <package>` 确认安装位置
- [ ] 检查实际目录结构，找到包含 `mcp.run()` 的入口模块
- [ ] 试运行确认启动时会输出哪些内容到 stdout

### 4.2 后端集成
- [ ] 如服务器有 stdout 污染，创建包装脚本 patch `print`
- [ ] 使用 `sys.executable` 而非硬编码 `"python"`
- [ ] 设置 `tool_name_prefix=True` 避免命名冲突
- [ ] 确定合理的清理方式（通常是释放引用即可）
- [ ] 三端（CLI / QQ Bot / Web API）同步集成
- [ ] 在 `tool_extractors.py` 注册 extractor（精确匹配或前缀匹配），让前端能获取结构化数据

### 4.3 前端集成
- [ ] 创建气泡组件（可复用/通用，或专用展示），优先读取 `toolCall.toolData`
- [ ] 注册到 registry（精确匹配或前缀匹配）
- [ ] 添加 display name

### 4.4 验证
- [ ] `await init_mcp_tools()` 能返回工具列表
- [ ] 调用任意工具能得到正确结果
- [ ] 进程退出时 MCP 子进程正确终止

---

## 五、参考

- [langchain-mcp-adapters](https://github.com/langchain-ai/langchain-mcp-adapters) — 官方文档
- [skills/mcp.py](../skills/mcp.py) — MCP 工具管理器实现
- [scripts/mcp_word_server.py](../scripts/mcp_word_server.py) — 包装脚本
- [WordBubble.vue](../web/src/components/tools/WordBubble.vue) — 前端气泡
- [registry.ts](../web/src/components/tools/registry.ts) — 工具注册表
