# Kaleidoscope Project — 工具调用气泡开发指南

## 一、项目概述

**Kaleidoscope Project**（万花筒计划）的目标是：让 WebUI 中每一个工具调用的气泡在**风格统一**的前提下，呈现**细节各异的交互组件**。

### 1.1 现状

当前所有工具调用由 [ToolCallCard.vue](../web/src/components/ToolCallCard.vue) 统一渲染——一个可折叠的卡片，以 KV 列表、代码块或 Markdown 三种方式展示参数和结果。无论调用的是天气查询、视频下载、地图搜索还是 PDF 阅读，外观和交互完全一致。

### 1.2 愿景

| 工具 | 现状 | 万花筒目标 |
|------|------|-----------|
| `bilibili_download` | 显示 JSON 输出 | 缩略图 + 标题 + 进度条 + **「从本地打开」按钮** |
| `weather` | 显示 JSON 输出 | 天气图标 + 温度曲线 + 城市名 |
| `map_nearby` | 显示 JSON 输出 | 地图卡片 + POI 列表 |
| `todo_add` | 显示 JSON 输出 | 勾选动画 + 项目详情 |
| `tarot` | 显示 JSON 输出 | 塔罗牌面 + 解读卡片 |
| ... | ... | ... |
| 未开发工具 | — | **沿用现有统一气泡**（渐进迁移） |

### 1.3 核心原则

1. **风格统一，组件各异** — 所有气泡共享外层 chrome（圆角、边框、间距、状态图标），但内容区域由各工具自由定义
2. **渐进迁移** — 未开发到工具继续使用 `ToolCallCard`，不影响现有功能
3. **Playground 先行** — 任何一个工具气泡必须在 Playground 页面验收通过后，才能部署到 WebUI
4. **类型安全** — 从 WebSocket 协议到 Vue 组件，全部使用 TypeScript 类型约束

---

## 二、架构设计

### 2.1 组件层次

```
ChatWindow.vue
  ├── MessageBubble.vue              (用户/助手消息，不变)
  ├── ThinkingBlock.vue              (思考过程，不变)
  └── ToolBubbleRouter.vue           ★ 新增：工具气泡路由
        ├── [已开发工具] → tools/XxxBubble.vue     (工具专属气泡)
        └── [未开发工具] → ToolCallCard.vue         (现有统一气泡，兜底)
```

**关键决策：** 不直接修改 `ChatWindow.vue` 中的 `ToolCallCard` 引用，而是插入一个 `ToolBubbleRouter` 组件，由它根据 `tool_name` 决定渲染哪个气泡。

### 2.2 文件结构

```
web/src/
├── components/
│   ├── ToolCallCard.vue              # 现有通用卡片（保留，作为兜底）
│   ├── ToolBubbleRouter.vue          # ★ 新增：气泡路由器
│   └── tools/                        # ★ 新增：各工具专属气泡目录
│       ├── _shared/                  # 共享子组件与样式
│       │   ├── BubbleChrome.vue      # 统一气泡外壳（状态图标、耗时、折叠）
│       │   ├── KvTable.vue           # 通用 KV 表（从 ToolCallCard 抽取）
│       │   └── shared.css            # 工具气泡共享样式变量
│       ├── BilibiliDownloadBubble.vue
│       ├── WeatherBubble.vue
│       ├── MapNearbyBubble.vue
│       └── ...                       # 随开发进度增加
├── types/
│   └── index.ts                      # ★ 扩展 ToolCall 类型，增加 tool_data 字段
└── views/
    └── PlaygroundView.vue            # ★ 新增：Playground 验收页面
```

### 2.3 路由扩展

```
router/index.ts 新增:
  { path: '/playground', name: 'playground', component: PlaygroundView }
```

---

## 三、核心类型设计

### 3.1 扩展 WebSocket 协议

当前 `tool_end` 事件的 `output` 字段是一个被截断的字符串（300 字符），不包含结构化数据。Kaleidoscope 需要后端在 `tool_end` 时携带工具专属的结构化数据。

```typescript
// types/index.ts 扩展

export interface ToolEndEvent {
  type: 'tool_end'
  payload: {
    tool_name: string
    output: string              // 保留：供未开发工具和降级显示
    elapsed: number
    tool_data?: Record<string, unknown>  // ★ 新增：工具专属结构化数据
  }
}

// tool_data 示例：
// bilibili_download: { video_title, cover_url, file_path, duration, filesize_mb }
// weather:          { city, temp, humidity, icon_code, forecast: [...] }
// map_nearby:       { pois: [{name, address, distance, lat, lng}], center: {...} }
```

### 3.2 前端 ToolCall 类型扩展

```typescript
export interface ToolCall {
  kind: 'tool'
  name: string
  input: string
  output: string | null
  elapsed: number | null
  status: 'running' | 'done' | 'error'
  toolData?: Record<string, unknown>  // ★ 新增：来自 tool_end.tool_data
}
```

### 3.3 工具气泡组件接口

所有工具专属气泡组件遵循统一的 Props 和 Emits 接口：

```typescript
// 每个 tools/XxxBubble.vue 必须实现的接口
export interface ToolBubbleProps {
  toolCall: ToolCall
}

// 工具气泡可触发的事件（由 BubbleChrome 或自身触发）
export interface ToolBubbleEmits {
  (e: 'action', payload: { action: string; data?: unknown }): void
  // 例如: emit('action', { action: 'open-file', data: { path: '...' } })
}
```

---

## 四、BubbleChrome — 统一气泡外壳

### 4.1 职责

`BubbleChrome.vue` 提供所有工具气泡共享的外层结构，确保视觉一致性：

- **状态图标**：运行中 (spinner) / 成功 (✓) / 失败 (✗)
- **工具名称**：从 `toolCall.name` 映射为中文显示名
- **耗时显示**：`toolCall.elapsed` 格式化
- **折叠/展开**：点击 header 切换，运行中自动展开
- **内容插槽**：`<slot />` 由各工具组件填充内容区域

### 4.2 模板结构

```
┌─────────────────────────────────────────────┐
│ ⟳ ｜ 视频下载 · bilibili_download    2.3s │  ← BubbleChrome header
│─────────────────────────────────────────────│
│                                             │
│  [工具专属内容区域]                          │  ← <slot />
│                                             │
│  ┌──────────────┐  ┌──────────────────┐     │
│  │ 从本地打开    │  │ 复制下载链接      │     │  ← 工具专属交互组件
│  └──────────────┘  └──────────────────┘     │
│                                             │
└─────────────────────────────────────────────┘
```

### 4.3 与 ToolCallCard 的兼容

`BubbleChrome` 的视觉风格应与 `ToolCallCard` 保持兼容——相同的 CSS 变量、圆角、边框颜色、状态颜色——使得新旧气泡在同一个聊天流中不显突兀。

---

## 五、ToolBubbleRouter — 气泡路由器

### 5.1 职责

根据 `toolCall.name` 查找注册表，决定渲染哪个组件。未注册的工具降级到 `ToolCallCard`。

### 5.2 实现

```typescript
// 工具注册表 — 每个新工具气泡在此注册
const toolBubbleRegistry: Record<string, Component> = {
  'bilibili_download':  defineAsyncComponent(() => import('./tools/BilibiliDownloadBubble.vue')),
  'weather':            defineAsyncComponent(() => import('./tools/WeatherBubble.vue')),
  'map_nearby':         defineAsyncComponent(() => import('./tools/MapNearbyBubble.vue')),
  // ... 渐进扩充
}
```

`ToolBubbleRouter.vue` 在 `<script setup>` 中使用 `computed` 查找注册表；命中则渲染对应组件，未命中则渲染 `ToolCallCard`。

---

## 六、Playground 验收页面

### 6.1 设计目标

Playground 是一个**开发辅助页面**，不属于生产用户流程。它允许开发者：

1. 看到所有已注册工具的气泡（包括已开发和未开发的）
2. 切换不同的状态（running / done / error）
3. 用鼠标点击交互组件（按钮、链接、折叠等）
4. 在真实的浏览器环境中验证视觉效果

### 6.2 页面布局

```
┌──────────────────────────────────────────────────────┐
│  Kaleidoscope Playground                     [侧栏]  │
│                                                      │
│  ┌─ 工具列表 ──────────────────────────────────────┐ │
│  │ [bilibili_download] [weather] [map_nearby] ...  │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  ┌─ 状态切换 ──────────────────────────────────────┐ │
│  │ [running] [done] [error]                        │ │
│  └────────────────────────────────────────────────┘ │
│                                                      │
│  ┌─ 气泡预览 ──────────────────────────────────────┐ │
│  │                                                  │ │
│  │  (当前选中工具的气泡，使用 mock 数据渲染)         │ │
│  │                                                  │ │
│  └──────────────────────────────────────────────────┘ │
│                                                      │
│  ┌─ 交互日志 ──────────────────────────────────────┐ │
│  │ emit('action', { action: 'open-file' }) 触发    │ │
│  └──────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────┘
```

### 6.3 Mock 数据

Playground 使用预定义的 mock 数据。每个工具需提供至少一组 mock `ToolCall` 对象：

```typescript
// tools/__mocks__/index.ts
export const toolMocks: Record<string, ToolCall[]> = {
  bilibili_download: [
    {
      kind: 'tool',
      name: 'bilibili_download',
      input: '{"url": "https://www.bilibili.com/video/BV1xx411c7mD"}',
      output: '下载完成',
      elapsed: 2.35,
      status: 'done',
      toolData: {
        video_title: '【4K】测试视频',
        cover_url: 'https://example.com/cover.jpg',
        file_path: 'output/BV1xx411c7mD.mp4',
        duration: '03:24',
        filesize_mb: 48.5,
      },
    },
    { /* running 状态 */ },
    { /* error 状态 */ },
  ],
  weather: [ /* ... */ ],
  // ...
}
```

### 6.4 验收清单

每个工具气泡在 Playground 中必须通过以下验收：

- [ ] 三种状态（running / done / error）视觉正确
- [ ] 折叠/展开动画流畅
- [ ] 所有交互按钮可点击，action 事件正确触发
- [ ] 超长文本/超长列表不破坏布局
- [ ] 暗色/亮色主题（如果后续支持）下均可读
- [ ] 移动端宽度（375px）下布局不溢出
- [ ] `toolData` 缺失时优雅降级（不报错、不白屏）

---

## 七、开发工作流

### 7.1 新增一个工具气泡的完整流程

```
1. 后端：在 tool_end 事件中添加 tool_data
   └── api/callbacks/websocket_callback.py

2. 前端类型：更新 ToolCall 和 WebSocket 事件类型
   └── web/src/types/index.ts

3. 前端组件：创建 tools/XxxBubble.vue
   └── web/src/components/tools/XxxBubble.vue

4. 注册：在 ToolBubbleRouter 的 registry 中注册
   └── web/src/components/ToolBubbleRouter.vue

5. Mock 数据：添加 Playground 用的 mock 数据
   └── web/src/components/tools/__mocks__/index.ts

6. Playground 验收：在 /playground 页面逐项检查验收清单

7. 部署：确认通过后，合并到 main 分支，部署到 WebUI
```

### 7.2 示例：实现 bilibili_download 气泡

#### Step 1 — 后端扩展 tool_data

```python
# api/callbacks/websocket_callback.py — on_tool_end 修改

import json

async def on_tool_end(self, output: str, **kwargs: Any) -> None:
    run_id = str(kwargs.get("run_id", ""))
    elapsed = time.time() - self._tool_start_time.pop(run_id, time.time())
    tool_name = self._tool_names.pop(run_id, "unknown")

    out_str = str(output) if not isinstance(output, str) else output

    # 提取工具输出的结构化数据
    tool_data = None
    try:
        if tool_name == "bilibili_download":
            data = json.loads(output) if isinstance(output, str) else output
            tool_data = {
                "video_title": data.get("title"),
                "cover_url": data.get("cover_url"),
                "file_path": data.get("file_path"),
                "duration": data.get("duration"),
                "filesize_mb": data.get("filesize_mb"),
            }
        # elif tool_name == "weather": ...
    except (json.JSONDecodeError, AttributeError):
        pass

    if len(out_str) > 300:
        out_str = out_str[:300] + f"... (共 {len(out_str)} 字符)"

    await self._ws.send_json({
        "type": "tool_end",
        "payload": {
            "tool_name": tool_name,
            "output": out_str,
            "elapsed": round(elapsed, 2),
            "tool_data": tool_data,  # ★ 新增
        },
    })
```

#### Step 2 — 更新前端类型

```typescript
// web/src/types/index.ts

export interface ToolEndEvent {
  type: 'tool_end'
  payload: {
    tool_name: string
    output: string
    elapsed: number
    tool_data?: Record<string, unknown>  // ★
  }
}

export interface ToolCall {
  kind: 'tool'
  name: string
  input: string
  output: string | null
  elapsed: number | null
  status: 'running' | 'done' | 'error'
  toolData?: Record<string, unknown>  // ★
}
```

#### Step 3 — 更新 useChat.ts 处理 tool_data

```typescript
// web/src/composables/useChat.ts — handleEvent 中的 tool_end case

case 'tool_end': {
  const tc = findRunningTool(turn.events, event.payload.tool_name)
  if (tc) {
    tc.output = event.payload.output
    tc.elapsed = event.payload.elapsed
    tc.status = 'done'
    tc.toolData = event.payload.tool_data  // ★
  }
  break
}
```

#### Step 4 — 创建专属气泡组件

```vue
<!-- web/src/components/tools/BilibiliDownloadBubble.vue -->
<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 成功状态 -->
    <div v-if="toolCall.status === 'done' && toolCall.toolData" class="bilibili-result">
      <img
        v-if="toolCall.toolData.cover_url"
        :src="toolCall.toolData.cover_url"
        class="video-cover"
      />
      <div class="video-info">
        <div class="video-title">{{ toolCall.toolData.video_title }}</div>
        <div class="video-meta">
          <span>时长 {{ toolCall.toolData.duration }}</span>
          <span>{{ toolCall.toolData.filesize_mb }} MB</span>
        </div>
      </div>
      <div class="video-actions">
        <button class="action-btn primary" @click="openLocal">
          从本地打开
        </button>
        <button class="action-btn" @click="copyPath">
          复制文件路径
        </button>
      </div>
    </div>

    <!-- 下载中 -->
    <div v-else-if="toolCall.status === 'running'" class="download-progress">
      <span class="spinner-sm"></span>
      <span>正在下载...</span>
    </div>

    <!-- 错误 -->
    <div v-else class="error-msg">{{ toolCall.output }}</div>
  </BubbleChrome>
</template>

<script setup lang="ts">
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'

const props = defineProps<{ toolCall: ToolCall }>()
const emit = defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

function openLocal() {
  const path = props.toolCall.toolData?.file_path
  if (!path) return
  // 通过 API 触发后端打开本地文件
  emit('action', { action: 'open-file', data: { path } })
}

function copyPath() {
  const path = props.toolCall.toolData?.file_path
  if (!path) return
  navigator.clipboard.writeText(String(path))
}
</script>
```

#### Step 5 — 注册

```typescript
// web/src/components/ToolBubbleRouter.vue

import { defineAsyncComponent } from 'vue'
import BilibiliDownloadBubble from './tools/BilibiliDownloadBubble.vue'

const registry: Record<string, Component> = {
  'bilibili_download': BilibiliDownloadBubble,
  // 后续工具逐一注册
}
```

#### Step 6 — Playground 验收

在 Playground 中添加 mock 数据，切换 running/done/error 三种状态，点击「从本地打开」和「复制文件路径」按钮，确认 action 事件正确触发，布局无溢出。

---

## 八、后端对应修改指南

### 8.1 WebSocket 回调扩展点

[websocket_callback.py](../api/callbacks/websocket_callback.py) 的 `on_tool_end` 方法需要支持提取工具专属的 `tool_data`。推荐方式：为每个工具提供一个轻量的数据提取函数。

```python
# 建议的文件结构（可选，根据复杂度决定）
api/callbacks/
├── websocket_callback.py        # 主回调，调用 tool_data 提取器
└── tool_data_extractors.py      # ★ 新增：各工具的 tool_data 提取函数
```

```python
# tool_data_extractors.py 示例

import json
from typing import Any

def extract_bilibili_download(output: str) -> dict[str, Any] | None:
    """从 bilibili_download 工具的输出中提取结构化数据。"""
    try:
        data = json.loads(output) if isinstance(output, str) else output
        return {
            "video_title": data.get("title"),
            "cover_url": data.get("cover_url"),
            "file_path": data.get("file_path"),
            "duration": data.get("duration"),
            "filesize_mb": data.get("filesize_mb"),
        }
    except (json.JSONDecodeError, AttributeError):
        return None


# 注册表
EXTRACTORS: dict[str, callable] = {
    "bilibili_download": extract_bilibili_download,
    # 后续工具在此注册
}
```

### 8.2 工具返回值的约定

为了让 `tool_data` 提取可靠，工具（Skill）的输出应遵循约定：

1. **输出应为 JSON 字符串**，而非自然语言描述
2. **JSON 中包含前端需要的所有字段**（标题、路径、缩略图 URL 等）
3. **字段命名使用 snake_case**（Python 惯例），在 tool_data 提取时转为 camelCase 给前端

---

## 九、共享子组件与样式规范

### 9.1 shared.css 变量

```css
/* tools/_shared/shared.css */
.tool-bubble-content {
  padding: 12px 16px 16px;
}

.tool-bubble-content .action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.tool-bubble-content .action-btn:hover {
  background: var(--bg-secondary);
  border-color: var(--accent-light);
}

.tool-bubble-content .action-btn.primary {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}

.tool-bubble-content .action-btn.primary:hover {
  opacity: 0.9;
}
```

### 9.2 通用子组件

从现有 `ToolCallCard.vue` 中抽取可复用的子组件到 `tools/_shared/`：

- **KvTable.vue** — KV 列表展示（当前 `ToolCallCard` 中的 `.kv-list` 部分）
- **CodeBlock.vue** — 代码块展示
- **SpinnerSm.vue** — 小型加载动画

这些子组件使得工具专属气泡不需要重复实现通用展示逻辑。

---

## 十、渐进迁移路线图

### Phase 1 — 基础设施（当前阶段）

- [x] 技术方案文档（本文档）
- [ ] `BubbleChrome.vue` — 统一气泡外壳
- [ ] `ToolBubbleRouter.vue` — 气泡路由器
- [ ] `PlaygroundView.vue` — Playground 验收页面
- [ ] 类型扩展（`ToolCall.toolData`、WebSocket `tool_data`）
- [ ] 后端 `tool_data` 提取框架
- [ ] 路由注册（`/playground`）

### Phase 2 — 首批工具气泡

- [ ] `bilibili_download` — 最优先（已有完整输出结构）
- [ ] `weather` — 天气卡片
- [ ] `map_nearby` — POI 列表

### Phase 3 — 逐工具迁移

按需将更多工具迁移到专属气泡，优先级由用户反馈和工具使用频率决定。

---

## 十一、注意事项

### 11.1 安全

- `tool_data` 中的 `file_path` 不应直接暴露给前端文件系统——打开文件操作应通过后端 API 代理
- 按钮触发的 `action` 事件在后端需做权限校验
- 用户输入的内容（如搜索关键词）在渲染时需转义

### 11.2 性能

- 工具气泡组件使用 `defineAsyncComponent` 实现按需加载，避免首屏 bundle 膨胀
- 缩略图等资源使用懒加载（`loading="lazy"`）
- 大量日志/输出使用虚拟滚动或分页

### 11.3 向后兼容

- `tool_data` 字段为可选——旧服务端不发送时，气泡降级到 `ToolCallCard`
- `ToolCallCard.vue` 不删除、不修改核心逻辑——始终作为兜底
- 已有的 WebSocket 事件类型保持兼容，仅做扩展

### 11.4 验收制度

> **任何一个工具气泡必须在 Playground 中通过全部验收清单后，才能部署到 WebUI。**

Playground 是 Kaleidoscope Project 的质量门禁。不允许绕过 Playground 直接修改 WebUI 中的工具展示逻辑。
