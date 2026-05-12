# SonettoHere v2.1 — Web 前端系统总览

## 前端是什么？

在软件开发中，"前端"指用户直接看到和交互的部分——界面、按钮、输入框、动画。对应的"后端"是服务器上运行的逻辑——处理数据、调用 API、与数据库交互。

SonettoHere v2.0 只有命令行（CLI）界面——用户在黑色终端里打字，AI 逐字回复。v2.1 的 `feat/web-ui` 分支新增了完整的 **Web 前端**，让用户通过浏览器以现代化的聊天界面与 AI 交互。

本系列文档（07-12）专为**前端初学者**编写，以本项目为案例，逐一讲解前端系统是如何构建的，以及它如何与后端通信。

---

## 技术栈一览

| 组件 | 技术选型 | 作用 |
|------|----------|------|
| UI 框架 | `Vue 3.4` | 构建交互式用户界面 |
| 页面路由 | `vue-router 4.3` | URL 变化时切换页面，无需刷新浏览器 |
| Markdown 渲染 | `marked 12` | 将 Markdown 文本转为 HTML |
| 构建工具 | `Vite 5` | 开发热更新 + 生产打包 |
| 类型系统 | `TypeScript 5.4` | 编译期类型检查，减少低级 bug |
| API 通信 | 原生 `fetch` + 原生 `WebSocket` | 与后端交换数据 |
| CSS 方案 | Scoped CSS + CSS Variables | 组件级样式隔离 + 全局主题变量 |

> **关键设计决策：零第三方依赖。** 前端没有使用 axios、Pinia、Element Plus 等常见库，而是全部使用浏览器原生 API（`fetch`、`WebSocket`）和 Vue 3 自带能力（`ref`、`reactive`、`composables`）。这使得代码非常透明——每个文件你都能看懂底层在发生什么。

---

## 绝对前后端分离

项目采用 **绝对前后端分离** 架构：

```
┌─────────────────────────────────────────┐
│  前端 (Vue 3 SPA)                       │
│  web/                                   │
│  ├── src/  (TypeScript + Vue 组件)       │
│  ├── dist/ (构建产物 → 纯 HTML+JS+CSS)   │
│  └── package.json                       │
│                                          │
│  ★ 有自己独立的进程、端口、构建系统       │
├─────────────────────────────────────────┤
│  后端 (Python FastAPI)                   │
│  api/                                   │
│  ├── server.py, routes/, callbacks/      │
│  └── agent/, memory/, skills/, config/   │
│                                          │
│  ★ 完全不知道前端实现细节，只提供 API     │
└─────────────────────────────────────────┘

通信方式：
  HTTP REST  ──→  会话管理、记忆读取
  WebSocket  ──→  实时聊天（流式 token 推送）
```

所谓"绝对分离"，意思是：

1. **前端和后端是两套独立运行的进程**。开发时，前端跑在 Vite 开发服务器（端口 5173），后端跑在 Uvicorn（端口 8000）。
2. **后端不渲染任何 HTML 模板**。没有 Jinja2，没有 `<div>{{ variable }}</div>`。后端只提供 JSON 数据和 WebSocket 事件流。
3. **前端不直接访问数据库或文件系统**。所有数据都通过 API 获取。
4. **前端有自己完整的工程体系**：`package.json`、`tsconfig.json`、`vite.config.ts`，与 Python 的 `pyproject.toml` 完全独立。

---

## 前端目录结构

```
web/
├── index.html                  # 浏览器入口 HTML（极简，只挂载 #app）
├── package.json                # 项目元数据与依赖声明
├── vite.config.ts              # Vite 构建配置 + 开发代理
├── tsconfig.json               # TypeScript 编译配置
├── tsconfig.node.json          # Vite 配置文件的 TypeScript 配置
│
├── dist/                       # 生产构建产物（可直接部署）
│   ├── index.html
│   └── assets/
│       ├── index-*.js          # 压缩后的 JS 包
│       └── index-*.css         # 压缩后的 CSS
│
└── src/                        # ★ 源代码（14 个文件）
    ├── main.ts                 #   Vue 应用入口
    ├── env.d.ts                #   TypeScript 类型声明（.vue 文件）
    ├── App.vue                 #   根组件：侧边栏 + 路由视图
    │
    ├── types/index.ts          #   ★ 所有 TypeScript 类型定义
    ├── api/index.ts            #   ★ REST API 客户端（fetch 封装）
    │
    ├── router/index.ts         #   路由配置（两个页面路由）
    │
    ├── composables/            #   ★ 组合式 API（状态逻辑复用）
    │   ├── useChat.ts          #     WebSocket 聊天状态管理
    │   └── useSession.ts       #     会话 CRUD 状态管理
    │
    ├── views/                  #   页面级组件（对应路由）
    │   ├── ChatView.vue        #     主聊天页面
    │   └── MemoryView.vue      #     长期记忆查看页
    │
    └── components/             #   可复用 UI 组件
        ├── ChatWindow.vue      #     消息列表（含自动滚动）
        ├── ChatInput.vue       #     输入框（含自动伸缩）
        ├── MessageBubble.vue   #     单条消息气泡
        ├── ThinkingBlock.vue   #     LLM 思考过程展示
        ├── ToolCallCard.vue    #     工具调用详情卡片
        ├── SessionSidebar.vue  #     会话列表（创建/切换/删除）
        ├── MemoryPanel.vue     #     长期记忆叙事面板
        └── StatusBadge.vue     #     连接状态指示灯
```

只有 **14 个源码文件**，但覆盖了真实生产级 Web 应用的所有关键概念：路由、状态管理、API 通信、WebSocket 实时推送、CSS 主题变量。

---

## 一张图看懂单次对话的全流程

```
用户在浏览器输入 "你好，今天天气怎么样？"
         │
         ▼
  ChatInput.vue             用户按 Enter → emit('send', message)
         │
         ▼
  ChatView.vue              收到 @send 事件 → 调用 useChat.send()
         │
         ▼
  useChat.ts                JSON.stringify({type:"chat", payload:{message}})
         │                  通过 WebSocket 发送到后端
         ▼
════════════════════════════════════════════════════
  WebSocket /ws/chat/{session_id}
         │
         ▼
  chat.py                   解析 JSON → 调用 LangGraph astream_events()
         │
         ▼
  WebSocketCallback         将 LangChain 事件转为结构化 JSON:
         │                   - on_llm_start    → {type:"thinking_start"}
         │                   - on_llm_new_token → {type:"token", payload:{token:"天"}}
         │                   - on_tool_end      → {type:"tool_end", ...}
         │                   - on_chain_end     → {type:"answer", payload:{content:"今天..."}}
         │
════════════════════════════════════════════════════
         │
         ▼
  useChat.handleEvent()     收到每条 JSON → 更新 reactive 状态
         │
         ├── thinking_start  → turn.thinking.push({tokens:'', done:false})
         ├── token           → turn.thinking[last].tokens += "天"
         ├── tool_start      → turn.toolCalls.push({name, input, status:'running'})
         ├── tool_end        → tc.status='done'; tc.output=...
         ├── answer          → turn.finalAnswer = content
         └── done            → turns.push(currentTurn); currentTurn=null
         │
         ▼
  Vue 响应式系统             状态变化自动触发 DOM 更新
         │
         ▼
  浏览器渲染                 用户看到 AI 的回答逐字出现
```

关键观察：
- 后端**不关心**前端用什么框架（Vue/React/原生 JS 都可以）
- 前端**不关心**后端怎么生成 AI 回复（LangChain/LangGraph/直接调 API 都可以）
- 两端通过**明确的协议**（JSON 消息类型定义）解耦

---

## 前端系统设计的四大原则

### 1. 类型先行

[`web/src/types/index.ts`](../web/src/types/index.ts) 是第一块基石。在写任何 UI 代码之前，先定义好所有的数据类型：

```typescript
// 服务端→客户端的每条 WebSocket 事件都有专属类型
export interface ThinkingStartEvent { type: 'thinking_start'; payload: { timestamp: number } }
export interface TokenEvent { type: 'token'; payload: { token: string } }
export interface ToolStartEvent { type: 'tool_start'; payload: { tool_name: string; input: string } }
// ... 共 10 种事件类型

// 客户端→服务端的消息也如此
export interface ChatMessage { type: 'chat'; payload: { message: string } }
export interface CancelMessage { type: 'cancel'; payload: Record<string, never> }

// UI 状态类型
export interface ChatTurn { id: string; userMessage: string; thinking: ThinkingBlock[]; ... }
```

这相当于前后端之间的**契约**——TypeScript 编译器保证前端只发送后端期望的消息格式，也只处理后端承诺返回的事件格式。

### 2. 关注点分离

每个文件只做一件事：

| 关注点 | 文件 | 职责 |
|--------|------|------|
| "数据长什么样" | `types/index.ts` | 类型定义 |
| "怎么和后端说话" | `api/index.ts` | REST 请求 |
| "怎么保持 WebSocket 连接" | `composables/useChat.ts` | WebSocket 生命周期 |
| "怎么管理会话列表" | `composables/useSession.ts` | 会话 CRUD |
| "聊天页面长什么样" | `views/ChatView.vue` | 页面布局 |
| "消息气泡长什么样" | `components/MessageBubble.vue` | 纯展示 |

### 3. 单向数据流

数据永远从父组件流向子组件，事件从子组件冒泡到父组件：

```
App.vue (持有 sessionId, sessions 状态)
  │  ├── props: sessions, activeId
  │  ├── emits: create, switch, delete
  │  ▼
  SessionSidebar.vue
  │
  │  ├── props: turns, currentTurn, error
  │  ▼
  ChatWindow.vue
  │  ├── props: block
  │  ▼
  ThinkingBlock.vue  (纯展示，无任何状态)
```

子组件**从不修改** props，只通过 `emit` 事件通知父组件。这确保了数据流是可预测、可调试的。

### 4. 原生优先

不引入 axios（HTTP 客户端库）、不引入 Pinia（状态管理库）、不引入 UI 组件库。所有功能用 Vue 3 自带能力 + 浏览器原生 API 实现。对于初学者，这意味着：你学的每个 API 都在浏览器标准文档里能找到，不被框架锁定。

---

## 前后端通信协议一览

### 通道一：REST API（HTTP）

| 方法 | 端点 | 前端调用者 | 用途 |
|------|------|-----------|------|
| POST | `/api/sessions` | `useSession._createSession()` | 创建新会话 |
| GET | `/api/sessions` | `useSession.refreshSessions()` | 列出所有会话 |
| GET | `/api/sessions/{id}` | `useSession.initIfNeeded()` | 获取单个会话信息 |
| DELETE | `/api/sessions/{id}` | `useSession.deleteSession()` | 删除会话 |
| GET | `/api/narrative` | `MemoryPanel.refresh()` | 读取长期记忆叙述 |

### 通道二：WebSocket（双向实时通信）

| 方向 | 消息类型 | 何时发送 |
|------|---------|---------|
| 客户端→服务端 | `chat` | 用户发送消息 |
| 客户端→服务端 | `cancel` | 用户点击"停止"按钮 |
| 客户端→服务端 | `ping` | 心跳保活（预留） |
| 服务端→客户端 | `thinking_start` | LLM 开始推理 |
| 服务端→客户端 | `token` | LLM 逐 token 输出 |
| 服务端→客户端 | `thinking_end` | LLM 推理结束 |
| 服务端→客户端 | `tool_start` | 工具开始执行 |
| 服务端→客户端 | `tool_end` | 工具执行完成 |
| 服务端→客户端 | `tool_error` | 工具执行出错 |
| 服务端→客户端 | `answer` | Agent 生成最终回答 |
| 服务端→客户端 | `done` | 当前回合全部结束 |
| 服务端→客户端 | `error` | 错误信息（如取消） |
| 服务端→客户端 | `pong` | 心跳应答 |

---

## 阅读路线

从本章开始，前端系列文档按以下顺序引导你从零理解整个前端系统：

| 序号 | 文档 | 你将学到 |
|------|------|----------|
| 8 | [Vue 3 组件树与响应式数据流](08-Vue3组件树与响应式数据流.md) | Vue SFC 结构、`ref`/`reactive`、props/emits、组件嵌套 |
| 9 | [前端路由与组合式 API](09-前端路由与组合式API.md) | Vue Router、Composables 模式、`useChat`/`useSession` 源码剖析 |
| 10 | [REST API 与前后端数据交互](10-REST与前后端数据交互.md) | `fetch` API、类型安全请求、会话管理完整流程 |
| 11 | [WebSocket 实时流式通信](11-WebSocket实时流式通信.md) | WebSocket 协议、事件驱动架构、流式 token 渲染、取消机制 |
| 12 | [从开发到生产：前端工程化](12-从开发到生产：前端工程化.md) | Vite 代理、构建流程、FastAPI 静态文件服务、部署架构 |

建议按顺序阅读。每篇文档都以本项目中的真实代码为案例，配合注释讲解每个关键概念。读完整个系列后，你将具备独立搭建一个 Vue 3 + FastAPI 全栈项目的基础能力。

---

← [客户端与回调系统](06-客户端与回调系统.md) | [Vue 3 组件树与响应式数据流](08-Vue3组件树与响应式数据流.md) →
