![首页](images/%E9%A6%96%E9%A1%B5.png)

# SonettoHere

基于 LangChain + LangGraph 的 ReAct AI Agent，支持 **多 LLM 提供商**、**SubAgent**、**Anthropic Skill 体系**。

## Quick Start

### 0. 克隆仓库

```bash
git clone https://github.com/Miso2233/SonettoHere.git
cd SonettoHere
```

### 1. 安装

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置

```bash
# 首次启动会自动创建 .env，或手动复制：
cp .env.example .env
```

**最少只需填写** `DEEPSEEK_API_KEY` 即可开始对话。

### 3. 启动

**推荐（Windows）：** 双击 `start.bat` 一键启动后端 + 前端，自动打开浏览器。

**手动启动：**

```bash
# 终端 1 — 后端
python main.py

# 终端 2 — 前端（开发模式）
cd web && npm install && npm run dev
```

浏览器访问 `http://localhost:5173`。

启动前建议编辑 `config/personas/` 下的文件以获得更贴合你的对话体验：
- `USER.md` — 你的自述信息
- `SOUL.md` — AI 性格设定

---

## 核心亮点

### 🎆 Anthropic Skill 体系

项目根目录的 `anthropic_skills/` 存放可复用的 **Anthropic Skill** 文件，每个子目录包含 `SKILL.md` 作为主文档。启动时系统自动扫描所有 SKILL.md 的元数据（名称、描述、路径）注入到提示词中，Agent 在需要时通过文件工具按需读取完整内容并执行。

大家可以从网上任意下载 Anthropic Skill 文件放到 `anthropic_skills/` 目录下，即可在对话中使用。

![系统状态](images/%E7%B3%BB%E7%BB%9F%E7%8A%B6%E6%80%81.png)

### 🔄 SubAgent 

内置 `call_sub_agent` 工具，支持在对话中**创建独立的SubAgent 会话**执行子任务：

- **隔离上下文**：SubAgent 拥有独立的上下文窗口，不污染主对话
- **嵌套限制**：最多 2 层嵌套，防止无限递归
- **前后端双通道**：前端 WebSocket 连接时实时流式输出；前端未连接时自动切换后端静默执行
- **兜底提取**：即使事件流未捕获到最终回答，也能从 checkpoint 持久化状态中可靠读取

适用于代码分析、多步骤搜索、文件处理等需要独立推理空间的场景。

### 🌐 多 LLM 提供商（Project Bay）

支持动态切换和组合多家 LLM 提供商：

- **预配提供商**：`providers.yaml` 中配置多家 API Key
- **运行时切换**：前端对话时按消息粒度指定 `provider_id` + `model_name`
- **健康自检**：后端可以检查各提供商的连通性和延迟
- **模型发现**：自动探测提供商支持的模型列表

主 LLM 不可用时自动降级到备用提供商，保障服务连续性。

![模型提供商](images/%E6%A8%A1%E5%9E%8B%E6%8F%90%E4%BE%9B%E5%95%86.png)

---

## 能力概览

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
| **B站** | 视频下载 | — |

> 所有 Key 仅在用到对应 Tool 时必需，不影响基础对话。

---

## 界面预览

| 首页对话 | 系统状态悬停 | 模型提供商管理 |
|---|---|---|
| ![首页](images/%E9%A6%96%E9%A1%B5.png) | ![系统状态](images/%E7%B3%BB%E7%BB%9F%E7%8A%B6%E6%80%81.png) | ![模型提供商](images/%E6%A8%A1%E5%9E%8B%E6%8F%90%E4%BE%9B%E5%95%86.png) |

---

## 项目结构

```
SonettoHere/
├── main.py                   # 入口
├── pyproject.toml
├── requirements.txt
├── .env.example
├── providers.yaml            # 多 LLM 提供商配置
├── anthropic_skills/         # Anthropic Skill 目录（自动扫描注入）
│   └── skill-creator/        #   示例：技能创建器
│
├── agent/
│   ├── graph.py              # LangGraph create_react_agent
│   ├── state.py              # AgentState
│   └── prompts.py            # 系统提示词组装（含 skill 扫描注入）
│
├── config/
│   └── personas/
│       ├── AGENTS.md         # 行为规则 + skill 使用指导
│       ├── SOUL.md           # 性格设定
│       └── USER.md           # 用户自述
│
├── memory/
│   ├── memory_manager.py     # YAML 持久化存储
│   ├── narrative.py          # 长期记忆异步引擎
│   └── user_init.py
│
├── tools/                     # 30+ Built-in Tool
│   ├── base.py                 # ToolBase 基类
│   ├── __init__.py
│   └── {todo,map,network,...}/
│
├── api/                      # FastAPI 后端
│   ├── server.py             # 应用工厂
│   ├── health.py             # 健康自检（LLM/记忆/工具/A_SKILLS/提供商）
│   └── routes/
│       ├── chat.py           # WebSocket 流式对话
│       ├── providers.py      # 提供商 CRUD
│       └── ...
│
├── web/                      # Vue 3 + Vite 前端
├── tests/
└── docs/
```

## 架构

```
用户输入 → [Agent: LLM + bind_tools] → [Tools: 执行] → 循环
              ↑                                    ↓
              │                    [final answer / 返回文档]
              └── LLM 读完文档后继续循环，下一步带真实参数调用

SubAgent ：
主 Agent → call_sub_agent → 创建子会话 → 独立 Agent 执行 → 返回结果
                              ↑                    |
                              └── 前端流式输出 ←───┘
```

- **Agent 框架**：LangGraph `create_react_agent` + MemorySaver
- **多 LLM 后端**：DeepSeek / OpenAI / Anthropic / 任何 OpenAI 兼容 API
- **记忆系统**：短期记忆（token 阈值裁剪）+ 长期记忆（异步 YAML 持久化）
- **前端**：Vue 3 + Vite，WebSocket 实时流式对话

## License

MIT
