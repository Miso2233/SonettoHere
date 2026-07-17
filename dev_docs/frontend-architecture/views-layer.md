# 视图层 — `views/` + `router/`

## 层级定位

页面级容器，负责组合组件与 composables 形成完整页面。每个 view 对应一个路由，通过 router 映射到 URL 路径。

## 路由表

| 路径 | 名称 | 视图 | 导航位置 |
|---|---|---|---|
| `/` | `chat` | `ChatView.vue` | 侧栏主导航 |
| `/memory` | `memory` | `MemoryView.vue` | 侧栏主导航 |
| `/playground` | `news` | `NewsView.vue`（懒加载） | 侧栏底部"动态" |
| `/providers` | `providers` | `ProvidersView.vue`（懒加载） | 设置弹出菜单 |
| `/soul` | `soul` | `SoulView.vue`（懒加载） | 设置弹出菜单 |
| `/user` | `user` | `UserView.vue`（懒加载） | 设置弹出菜单 |
| `/path-whitelist` | `path-whitelist` | `PathWhitelistView.vue`（懒加载） | 设置弹出菜单 |
| `/sonetto-blocker` | `sonetto-blocker` | `SonettoBlockerView.vue`（懒加载） | 设置弹出菜单 |
| `/env-vars` | `env-vars` | `EnvVarsView.vue`（懒加载） | 设置弹出菜单 |

非懒加载路由（`ChatView`、`MemoryView`）在主包中，其余视图按需加载。

## 核心视图

### ChatView.vue — 主聊天页面

**作为 App 的默认首页，承载核心聊天功能**：

```
ChatView
├── header
│   ├── StatusBadge         — WS + 后端健康状态
│   ├── mode-tags           — 私密/自动执行/图像认知模式指示
│   ├── ContextUsageBadge   — Token 用量 + 模型名
│   └── TaskTrackerBar      — 任务追踪进度
├── ChatWindow              — 消息列表
│   ├── MessageBubble (user)
│   ├── ThinkingBlock / ToolBubbleRouter / MessageBubble (assistant)
│   └── 记忆更新日志
└── ChatInput               — 输入区
```

**数据连接**：

```typescript
const { sessionId, sessions } = useSession()
const { connected, isStreaming, turns, currentTurn, error, contextUsage,
        taskTrackerData, send, cancel, sendUserResponse, removeTurns,
        privateMode, setPrivateMode, autoApprove, setAutoApprove } = useChat(sessionId)
```

**扩展功能**：

- 无提供商时显示引导卡片
- 子 Agent 会话时显示只读提示栏（`isSubagent` 计算属性检测 `sessions` 列表）
- 撤回功能：`handleUndo()` → `api.undoMessages()` → `removeTurns()`
- 模型选择联动：`onModelChange()` 存储当前选中的提供商和模型
- 图像认知模式：`imageRecognition` 开关 → `provider.model_vision` 检测

### App.vue — 应用根组件

```
App Layout
├── sidebar
│   ├── Logo
│   ├── 导航链接
│   │   ├── 对话 (/)
│   │   └── 记忆 (/memory)
│   ├── 动态 NEWS (/playground)
│   ├── 设置弹出菜单
│   │   ├── 模型 (/providers)
│   │   ├── 人设 (/soul)
│   │   ├── 用户 (/user)
│   │   ├── 路径白名单 (/path-whitelist)
│   │   ├── 拒止锚 (/sonetto-blocker)
│   │   └── 环境变量 (/env-vars)
│   ├── SessionSidebar
│   └── HealthPanel
└── main
    └── <router-view />
```

**侧栏交互**：

```typescript
// 点击侧栏空白区域 → 折叠/展开
function onSidebarClick(e: MouseEvent) {
  if (e.target === e.currentTarget) toggleSidebar()
}

// 设置弹出菜单位置跟随触发器按钮
function updatePopupPosition() {
  const rect = settingsTriggerRef.value.getBoundingClientRect()
  popupTop.value = `${rect.top}px`
  popupLeft.value = `${rect.right + 8}px`
}
```

## 设计要点

### 1. 懒加载优化

除 `ChatView` 和 `MemoryView` 外，所有视图都使用动态 `import()` 实现懒加载：

```typescript
{
  path: '/providers',
  component: () => import('@/views/ProvidersView.vue'),  // 按需加载
}
```

这确保首屏包体积最小化（主包约 660KB → 230KB gzip）。

### 2. 子 Agent 只读模式

```typescript
const isSubagent = computed(() => {
  return sessions.value.some(
    s => s.session_id === sessionId.value && s.is_subagent
  )
})
```

当当前会话被标记为子 Agent 时，`ChatInput` 被替换为只读提示栏，用户无法在子会话中发送消息。

### 3. 设置弹出菜单的定位

设置菜单使用 `position: fixed` 通过 JS 计算位置（非 CSS 绝对定位），确保弹出菜单不会溢出侧栏边界或被侧栏的 `overflow: hidden` 裁剪。位置在点击时通过 `getBoundingClientRect()` 实时计算。
