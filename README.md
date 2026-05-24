# SonettoHere v1.0.0

基于 LangChain + LangGraph 的 ReAct AI Agent，内置 30 个 Skill。支持 CLI / Web / QQ Bot 三种运行模式。

## Quick Start

### 1. 安装

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 配置

运行后会自动从 `.env.example` 复制生成 `.env`，编辑并填写 API Key：

```bash
# 首次启动会自动创建 .env，或手动：
cp .env.example .env
```

**最少只需填写** `DEEPSEEK_API_KEY` 即可开始对话。其他 Key 按需填写（见下方 Skills 表）。

### 3. 启动

```bash
# CLI 模式（默认）
python main.py

# Web 模式（浏览器访问 http://localhost:5173）
python main.py web

# QQ Bot 模式
python main.py qqbot
```

首次启动会自动创建缺失的配置文件（`.env`、`USER.md`、`SOUL.md`）。

## 能力概览

SonettoHere 内置 **30 个 Skill**，每个 Skill 由 `SKILL.md`（领域知识文档）+ 执行代码组成，LLM 按需加载文档后再调用。

| 领域 | Skills | 需要配置 |
|------|--------|---------|
| **Todo** | 添加/列出/完成/取消/删除/更新/查询任务、列出项目 | `TODOIST_API_TOKEN` |
| **地图** | 周边搜索、地址编码、公交/骑行路线、模糊地址 | `AMAP_API_KEY` |
| **网络** | 天气查询、智能搜索、网页抓取、节假日日历 | `UAPIS_API_KEY` |
| **文件** | 读写删改、目录操作、PDF/Word 阅读 | — |
| **开发** | 语法检查、代码质量分析、单元测试、调试器 | — |
| **系统** | 当前时间、Python 脚本执行 | — |
| **任务追踪** | 多步骤任务进度管理 | — |
| **交互** | 向用户提问 | — |
| **娱乐** | 答案之书、塔罗牌 | `UAPIS_API_KEY` |
| **B站** | 视频下载 | — |

> 所有 Key 仅在用到对应 Skill 时必需，不会影响基础对话。

## 运行模式

### CLI 模式

```bash
python main.py
# 或
python main.py cli
```

交互命令：
- 直接输入问题开始对话
- `/clear` — 清空当前对话
- `/exit` — 退出

### Web 模式

```bash
python main.py web
# 另开终端启动前端 dev server
cd web && npm run dev
```

浏览器访问 `http://localhost:5173`，Web 界面支持：
- 多会话管理
- 实时流式对话
- 长期记忆查看
- 随机记忆卡片

### QQ Bot 模式

```bash
python main.py qqbot
```

基于 `qq-botpy` SDK，支持：
- C2C 私聊自动响应
- 多用户会话隔离
- 长期记忆异步持久化
- QQ 2000 字符自动截断

## 项目结构

```
SonettoHere/
├── main.py                  # 入口（自动初始化缺失文件）
├── pyproject.toml           # 项目元数据
├── requirements.txt         # 依赖
├── .env.example             # 环境变量模板
│
├── agent/
│   ├── graph.py             # LangGraph StateGraph
│   ├── state.py             # AgentState
│   └── prompts.py           # 系统提示词组装
│
├── config/
│   └── personas/            # 人设文件（首次启动自动创建）
│       ├── AGENTS.md        # 行为规则
│       ├── SOUL.md          # 性格设定（可自定义）
│       └── USER.md          # 用户自述（可编辑）
│
├── memory/
│   ├── memory_manager.py    # YAML 持久化存储引擎
│   ├── narrative.py         # 长期记忆异步引擎
│   └── user_init.py         # 文件自动初始化
│
├── skills/                  # 30 个 Skill
│   ├── base.py              # SkillBase 基类
│   ├── __init__.py          # 集中注册
│   └── {todo,map,network,...}/
│
├── clients/
│   ├── cli.py               # CLI 入口
│   └── qqbot.py             # QQ Bot 适配器
│
├── api/                     # FastAPI Web 服务
│   ├── server.py            # 应用工厂
│   └── routes/              # REST & WebSocket
│
├── web/                     # Vue 3 前端（需 npm run build）
├── tests/                   # 测试
└── docs/                    # 开发文档
```

## 架构

```
用户输入 → [Agent: LLM + bind_tools(skills)] → [Skills: 执行] → 循环
              ↑                                    ↓
              │                    [final answer / 返回文档]
              └── LLM 读完文档后继续循环，下一步带真实参数调用
```

- **LLM 后端**：DeepSeek Chat（OpenAI 兼容 tool calling）
- **Agent 框架**：LangGraph `create_react_agent` + MemorySaver
- **记忆系统**：短期记忆（token 阈值裁剪）+ 长期记忆（异步 YAML 持久化）
- **前端**：Vue 3 + Vite，实时流式对话
- **QQ Bot**：`qq-botpy` SDK，多用户隔离

## 致谢

- [bilibili-downloader](https://github.com/tyokyo320/bilibili-downloader) — B 站视频下载核心逻辑

## License

MIT
