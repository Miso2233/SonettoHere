![首页](images/%E9%A6%96%E9%A1%B5.png)

# SonettoHere

基于 LangChain + LangGraph 的 ReAct AI Agent，支持 **多 LLM 提供商**、**SubAgent**、**Anthropic Skill 体系**。

## 快速开始

### 前置要求

- **Python 3.10+**
- **Node.js 18+** — [下载](https://nodejs.org/)
- **API Key** — 推荐使用 DeepSeek（见下方说明）

### 1. 获取代码

```bash
git clone https://github.com/Miso2233/SonettoHere.git
cd SonettoHere
```

或直接下载 [ZIP 源码](https://github.com/Miso2233/SonettoHere/archive/refs/heads/main.zip) 并解压。

### 2. 一键初始化

```bash
python setup.py
```

或双击 `setup.bat`（推荐 Windows 用户）。

脚本会引导你完成全部 6 步：

| 步骤 | 内容 | 操作 |
|------|------|------|
| 1/6 | 检查 Node.js | 全自动 |
| 2/6 | 创建虚拟环境，安装 Python 依赖 | 全自动 |
| 3/6 | 安装前端 npm 包 | 全自动 |
| 4/6 | 生成 `.env` 配置文件 | 全自动 |
| **5/6** | **配置 LLM 提供商** | **手动输入** |
| **6/6** | **输入你的称呼，配置 AI 个性** | **手动输入** |

### 3. 配置 LLM 提供商

第 5 步会引导你输入 **Base URL** 和 **API Key**，脚本会自动测试连接并获取可用模型列表。

推荐使用 **DeepSeek**（性价比高，兼容 OpenAI API）：

1. 前往 [platform.deepseek.com](https://platform.deepseek.com/) 注册并申请 API Key
2. 在 setup.py 第 5 步中输入：

```
Base URL: https://api.deepseek.com/v1
API Key: sk-你的密钥
```

> 也支持任何 OpenAI 兼容 API（OpenRouter、Qwen、智谱等），只需填入对应的 Base URL 和 Key。

### 4. 启动

```bash
start.bat
```

或双击 `start.bat`，脚本会自动启动后端 + 前端并打开浏览器。

浏览器访问 `http://localhost:5173`，即可开始与 Sonetto 对话。

## 初次开始对话

打开页面后，你会看到 Sonetto 的聊天界面。可以直接在输入框打字发送：

```
你好，我是 [你的名字]。
```

在与Sonetto的聊天过程中，Sonetto将逐步建立对你的了解。这些信息会被记录在 `config/personas/memory.yaml` 中，成为 AI 对你的长期记忆。

你也可以直接提出具体需求：

```
帮我查一下明天北京的天气
搜索一下洛天依《海边城》的相关信息，我很喜欢这首歌
```

> **提示**：如果提示"暂无已配置的 LLM 提供商"，请先前往侧栏 **设置 → 模型** 添加 API Key。

## 固定会话

固定会话（Const Session）是可以**永久保存**的聊天会话，不会因服务重启或 TTL 过期而丢失。

- **固定会话**：在侧边栏会话列表右键任一普通会话 → **固定会话**，输入名称即可保存。点击按钮可自动生成名称。
- **解绑固定**：右键已固定的会话 → **取消固定**
- 固定会话的数据存储在 `api/data/const_sessions.yaml`，服务启动时自动加载
- 适合保存常用的工具性会话、特定角色的对话场景

## 设置性格与用户偏好

在页面栏 **设置 → 人设 / 用户** 中可直接在线编辑，自定义 AI 的性格和它对你的了解：

| 文件 | 用途 | 示例 |
|------|------|------|
| `SOUL.md` | AI 的人设、性格、说话风格 | "你是 Sonetto，一位温柔细腻的 AI 助手" |
| `USER.md` | 你的基本信息和偏好 | "用户是一名全栈开发者，喜欢简洁的回复" |
| `AGENTS.md` | AI 的工具使用策略等行为规则 | 预置了工具使用和调用规范 |
| `memory.yaml` | AI 自动记录的长期记忆 | 对话中积累的关于你的事实 |

`memory.yaml` 由 AI 在对话过程中自动维护。编辑后刷新页面即可生效，无需重启服务。

## 白名单与拒止锚机制

两道安全防线，保护你的文件系统：

**路径白名单**（`设置 → 路径白名单`）— 限制 AI 可读写的文件目录范围。未在白名单中的路径会被拒绝访问。默认只放行了项目自身目录的技能文件夹。

**SonettoBlocker 拒止锚**（`设置 → 拒止锚`）— 在敏感目录下放置一个 `.sonetto_blocker` 标记文件（锚）。AI 在访问任何文件前会检查路径中是否存在此标记，一旦发现立即阻断并复述自己的意图。

```
用法示例：在 `C:/重要文档/` 下创建拒止锚 →
AI 尝试读取该目录时会提示 "安全阻断" 并等待你确认
```

## Tools 工具

内置 30+ 个 Built-in Tool，涵盖日常工具链：

| 领域 | Tools | 需要配置 |
|------|--------|----------|
| **Todo** | 添加/列出/完成/取消/删除/更新/查询任务、列出项目 | `TODOIST_API_TOKEN` |
| **地图** | 周边搜索、地址编码、公交/骑行路线、模糊地址 | `AMAP_API_KEY` |
| **网络** | 天气查询、Tavily 搜索、Tavily 网页提取、节假日日历 | `UAPIS_API_KEY` + `TAVILY_API_KEY` |
| **文件** | 读写删改、目录操作、PDF/Word 阅读 | — |
| **开发** | 语法检查、代码质量分析、单元测试、调试器 | — |
| **系统** | 当前时间、Python 脚本执行 | — |
| **SubAgent** | 创建独立会话执行复杂子任务 | — |
| **交互** | 向用户提问 | — |
| **娱乐** | 答案之书、塔罗牌 | `UAPIS_API_KEY` |

> 所有 Key 仅在用到对应 Tool 时必需，不影响基础对话。

## Skills 技能

Skills 是存放在 `anthropic_skills/` 目录下的独立技能包，每个子文件夹代表一个技能。AI 可以**自主识别并调用**这些技能来扩展能力边界。

可以在[SkillsMP](https://skillsmp.com/zh)等平台下载skill。

你也可以自行编写 Skills：在 `anthropic_skills/` 下创建新文件夹，放入 Markdown 指令文件即可。AI 会在适当时机自动加载并使用。

## Macros 宏

Macros 是比 Skills 更轻量的流程指引，本质是一篇带 YAML frontmatter 的 `MACRO.md` 文件，不含脚本或外部依赖。

- **触发方式**：在输入框中以 `!` 或 `！` 开头，自动提词器会提示可用的宏名称
- **定义**：每个宏存放在 `macros/<宏名称>/MACRO.md`，通过 frontmatter 中的 `type: macro` 标识
- **与 Skill 的关系**：宏是 Skill 基类的派生类。任何 Skill 都可以作为宏，特别是那些高度描述工作流、不含知识和脚本依赖的 Skill。宏也特别适合固化你个人的私人工作流。

### 内置宏

项目预置了 `macro-creator`——这是一个**关于宏的宏**（metamacro），当你想将某个稳定流程封装成可复用的宏时，直接说"把这个流程写成宏"，Agent 会引用它来引导你完成创建。

### 建立宏的过程

1. 在 `macros/` 下创建子目录 `macros/<macro-name>/`
2. 编写 `MACRO.md`，包含 YAML frontmatter：

```yaml
---
name: <宏的英文标识>
type: macro
version: 1.0
author: Sonetto
keywords: [关键词1, 关键词2]
description: 一句话描述触发场景，Agent 据此匹配宏
category: <分类名>
---
```

3. 正文按步骤描述工作流程，可包含适用场景、输入输出、示例对话
4. 保存后即可在输入框中用 `!<宏名称>` 触发

> Macro 的优势是轻量：无需修改代码、无需重启服务，新建一篇 Markdown 文件即可扩展 AI 的能力。

## MCP 服务器

SonettoHere 支持通过 MCP（Model Context Protocol）接入外部工具，只需编辑 `config/mcp_servers.yaml` 即可添加 MCP 服务器，无需改动代码。

支持 4 种传输类型：本地子进程（stdio）和远程连接（SSE / Streamable HTTP / WebSocket）。

### 配置字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `server_id` | ✓ | 唯一标识，将作为工具名前缀（`{server_id}_工具名`）|
| `enabled` | | 是否启用，`true`/`false`，默认为 `true` |
| `description` | | 人类可读的描述，仅用于展示 |
| `transport` | ✓ | 传输类型：`stdio` / `sse` / `streamable_http` / `websocket` |

#### stdio（本地子进程）

```yaml
- server_id: "my-server"
  enabled: true
  transport: "stdio"
  command: "node"           # 可执行文件路径
  args: ["server.js"]       # 命令行参数
  env:                       # 可选：环境变量
    API_KEY: "xxx"
  cwd: "/path/to/workdir"   # 可选：工作目录
```

#### SSE / Streamable HTTP / WebSocket（远程连接）

```yaml
- server_id: "remote-service"
  enabled: true
  transport: "streamable_http"   # 或 "sse" / "websocket"
  url: "https://example.com/mcp" # 服务端地址
  headers:                        # 可选：HTTP 请求头
    Authorization: "Bearer token"
  timeout: 30                     # 可选：连接超时（秒）
```

### 激活方式

- **重启后端**：自动读取配置
- **热加载**：调用 `POST /api/mcp/reload`，无需重启

### 注意事项

- 工具名称会自动添加 `{server_id}_` 前缀，避免多服务器间的命名冲突
- MCP 工具在前端统一使用 ToolCallCard 展示，无需注册专属气泡组件
- `config/mcp_servers.yaml` 已加入 `.gitignore`，不会提交到版本库

---

## 引用机制

SonettoHere 支持在输入框中引用多种类型的内容作为对话上下文：

| 引用类型 | 说明 | 触发方式 |
|----------|------|----------|
| **文件引用** | 引用项目中的任意文件 | 拖拽文件到输入框 |
| **文件夹引用** | 引用整个目录结构 | 拖拽文件夹到输入框 |
| **文本引用** | 引用已有消息内容 | 右键消息 → 引用 |
| **技能引用** | 指定使用某个 Skill | 手动输入 `@技能名` |
| **工具引用** | 指定使用某个 Tool | 手动输入 `#工具名` |
| **网页链接** | 引用 URL（预留） | 粘贴链接 |

输入@或#后，自动提词器将出现，提示您可能想选择的技能或工具。使用上下方向键和Tab键确认。

被引用的文件内容会作为上下文发送给 AI，方便它基于具体代码或文档内容进行回答。

> 输入框上方可拖拽调整高度，方便查看长文本。

## 私密模式

私密模式下，当前对话**不会被保存到长期记忆和本地存储**。关闭后恢复正常保存。

- **切换**：点击顶栏的「私密」按钮，或按 `Ctrl + K`
- **开启时**：对话内容仅存在于当前会话中，刷新页面后丢失
- **关闭时**：对话内容会被 AI 总结并写入 `memory.yaml`，形成长期记忆

适用于临时咨询、隐私话题等不需要被记住的对话场景。

## 检查与自动执行代码

对于每一个会话，你可以选择手动审核或自动放行Python工具：

| 模式 | 行为 | 适用场景 |
|------|------|----------|
| **检查**（默认） | AI 写出代码后等你确认才执行 | 不熟悉 AI 生成的代码时 |
| **自动** | AI 直接执行，无需确认 | 信任 AI、频繁调用工具的场合 |

- **切换**：点击顶栏的「检查/自动」按钮
- **安全提示**：AI 生成的代码可能包含意外操作。不确定时请保持「检查」模式。

---


## License

MIT
