# SonettoHere 前端架构

## 架构总览

前端采用 **Vue 3 Composition API + Pinia** 的单页应用架构，按职责分为 **5 个层级 + 1 个横向基础设施层**：

```
┌───────────────────────────────────────────┐
│              路由层 (router/)               │  页面路由分发
├───────────────────────────────────────────┤
│           视图层 (views/)                   │  页面级组件：组合功能模块
├───────────────────────────────────────────┤
│           组件层 (components/)              │  UI 展示组件 + 功能组件
├───────────────────────────────────────────┤
│           组合式层 (composables/)           │  业务逻辑：状态管理 + 事件处理
├───────────────────────────────────────────┤
│  ★ 状态管理层 (stores/) ★                 │  ★ 新增：Pinia 集中状态管理 ★
├───────────────────────────────────────────┤
│             基础设施层                      │
│  router/ (路由) + api/ (请求) + types/     │
│  + utils/ (工具) + assets/                 │
└───────────────────────────────────────────┘
```

## 依赖方向

依赖关系是**单向向下的**，上层依赖下层，下层不依赖上层：

```
views/ → components/ → composables/ → stores/ → api/ + types/ + utils/
  ↘ 直接调用 composables 暴露的响应式状态和 actions
```

## 模块清单

| 模块目录 | 层级 | 职责 |
|---|---|---|
| [stores/](stores-layer.md) | ① | Pinia 状态管理：聊天通道、会话、健康、侧栏 |
| [composables/](composables-layer.md) | ② | 组合式函数：业务逻辑编排、WebSocket 事件处理 |
| [components/](components-layer.md) | ③ | Vue 组件：聊天窗口、输入框、思考块、Markdown 渲染 |
| [views/](views-layer.md) | ④ | 页面视图：路由入口，组合组件与 composables |
| [router/](router-layer.md) | — | 路由定义：路径与视图映射 |
| [api/](api-layer.md) | — | HTTP API 封装：后端 REST 请求 |

## 请求处理流程

### 聊天消息流（核心路径）

```
ChatInput (@send)
  ↓
ChatView.onSend() → useChat.send()
  ↓
chatStore.send() → WebSocket.send(chat 消息)
  ↓
[后端处理 — 多轮 token 推送]
  ↓
chatStore.onmessage → handleEventForChannel()
  ↓
turnHandlers.get('token') → handleToken()
  ↓
lastThink.tokens += token  (响应式更新)
  ↓
ThinkingBlock.vue / RenderMarkdown.vue (v-html 重渲染)
```

### WebSocket 事件分发路径

```
WebSocket message → JSON.parse → ServerEvent
  ↓
handleEventForChannel(sid, event)
  ├── context_usage → ch.contextUsage = payload
  ├── sub_session_created → handleSubSessionCreated() (动态 import sessionStore)
  ├── memory_* (memoryHandlers Map)
  └── thinking_start / token / thinking_end / tool_start / tool_end /
      tool_error / answer / done / error / ask_user
      → turnHandlers Map → handler(ch, sid, turn, event)
```

## 关键技术栈

| 技术 | 用途 |
|---|---|
| **Vue 3** (Composition API + `<script setup>`) | UI 框架 |
| **Pinia** | 集中状态管理（替代模块级 reactive Map） |
| **Vue Router 4** | 前端路由 |
| **Vite 5** | 构建工具 |
| **markdown-it** + KaTeX | Markdown / 数学公式渲染 |
| **CodeMirror 6** | 代码 / Markdown 编辑器 |
| **原生 WebSocket** | 实时通信（无第三方 WS 库） |
| **原生 fetch** | HTTP 请求（无 Axios 等 HTTP 库） |
| **localStorage** | 对话历史客户端持久化 |

## 设计约定

1. **Composables 仅做编排** — 业务逻辑在 composables 中编排，状态在 Pinia stores 中管理，组件只负责渲染和用户交互
2. **无 Pinia 直接导入组件** — 组件通过 composables 间接使用 store（避免 store 接口变动时大面积修改组件）
3. **WebSocket 事件驱动 UI** — 所有聊天 UI 更新通过 WebSocket 事件驱动，无轮询
4. **流式渲染降级** — 流式接收期间禁用 iframe 沙箱（避免频繁重建），完成后按需启用
5. **localStorage 作为持久化缓存** — 会话消息缓存在 localStorage，页面刷新后恢复；容量上限 5MB，超限时静默失败
