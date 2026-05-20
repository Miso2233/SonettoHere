# 气泡右键上下文菜单设计文档

## 概述

为 Web UI 中所有聊天气泡（用户消息、AI 回复、思考过程、工具输出）添加了统一的右键上下文菜单。当前仅实现「引用」功能，但架构支持低成本扩展。

---

## 架构

### 组件层次

```
ChatView
 └── ChatWindow
      ├── .cite-source (wrapper)  ← @contextmenu.prevent
      │    └── MessageBubble / ThinkingBlock / ToolBubbleRouter
      ├── .cite-source (wrapper)
      │    └── ...
      └── ContextMenu  ← 全局唯一实例
```

- 每个气泡外层包裹 `div.cite-source`（`display: contents`，不影响布局），绑定 `@contextmenu.prevent`
- `ChatWindow` 持有唯一 `ContextMenu` 实例，通过状态控制显示/隐藏
- `ContextMenu` 使用 `<Teleport to="body">` 避免溢出裁剪

### 数据流

```
用户右键气泡
  → onBubbleContextMenu(event, sourceType, fullText, sourceLabel)
  → 检测 window.getSelection() 判断是否框选文字
  → 设置 pendingCitation + 菜单位置
  → 显示 ContextMenu
  → 用户点击菜单项
  → handleContextMenuSelect(action)
  → emit('cite', Citation) → ChatView → ChatInput
```

### Citation 类型

```typescript
interface Citation {
  id: string
  text: string
  sourceLabel: string        // 显示标签："用户"、"AI"、"思考过程"、工具名称
  sourceType: 'user_message' | 'assistant_message' | 'tool_result' | 'thinking'
}
```

---

## 核心机制

### 框选文字检测

```typescript
const selection = window.getSelection()
const selectedText = selection?.toString().trim()
if (selectedText && selection!.rangeCount > 0) {
  const range = selection!.getRangeAt(0)
  const target = event.currentTarget as HTMLElement | null
  if (target && target.contains(range.commonAncestorContainer)) {
    citeText = selectedText  // 仅引用选中部分
  }
  selection!.removeAllRanges()
}
```

- 使用 `event.currentTarget.contains()` 校验选中范围是否在当前气泡内
- 跨气泡选中自动回退到引用全文
- 选中后清除选区（`removeAllRanges`），避免干扰后续操作

### 引用文本截断

- 引用文本上限 1000 字符（`MAX_CITE_LENGTH`），超出尾部替换为 `…`
- 标签预览截断为 40 字符，完整文本通过 `title` 属性在 hover 时查看

---

## ContextMenu 组件

```vue
<ContextMenu
  :position="{ x, y }"
  :items="[{ label, action, icon? }]"
  :visible="boolean"
  @select="onSelect"
  @close="onClose"
/>
```

- 使用 `<Teleport to="body">` 渲染，避免父级 `overflow: hidden` 裁剪
- 半透明 backdrop 层拦截点击关闭 + 阻止原生右键菜单（使用 `v-show` 而非 `v-if`，确保动画正常工作）
- `document.addEventListener('keydown')` 监听 Escape 键关闭
- 菜单项通过 `items` prop 传入，组件本身不硬编码菜单内容

---

## 样式与动画参数

样式定义在 `web/src/components/ContextMenu.vue` 的 `<style scoped>` 中。

### 磨砂玻璃背景（`.context-menu`）

```css
.context-menu {
  background: color-mix(in srgb, var(--bg-card) 75%, transparent);
  backdrop-filter: blur(16px) saturate(1.2);
  border: 1px solid color-mix(in srgb, var(--border) 60%, transparent);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.15);
  border-radius: 8px;
  padding: 4px 0;
}
```

| 属性 | 含义 | 修改指导 |
|------|------|----------|
| `background: color-mix(… 75%, transparent)` | 背景色取自 `--bg-card`，75% 不透明度实现半透明 | 增大百分比（如 90%）→ 更不透明，磨砂感减弱；减小 → 更透明 |
| `backdrop-filter: blur(16px)` | 后方内容高斯模糊半径 | 增大（如 24px）→ 模糊更强，隐私性更好但可能晕眩；减小（如 8px）→ 更清晰 |
| `backdrop-filter: saturate(1.2)` | 色彩饱和度增强，补偿模糊导致的褪色 | 设为 1.0 可取消；增大 → 色彩更鲜艳 |
| `border: … 60%, transparent` | 边框颜色取自 `--border`，60% 不透明度 | 增大 → 边框更实；减小 → 边框更淡甚至消失 |
| `box-shadow: 0 4px 24px rgba(0,0,0,0.15)` | 阴影偏移 4px、虚化 24px、透明度 15% | 调大虚化或透明度 → 阴影更柔和；调小 → 阴影更锐利 |
| `border-radius: 8px` | 菜单圆角 | 增大（如 12px）→ 更圆润；减小（如 4px）→ 更方正 |
| `padding: 4px 0` | 菜单项与容器边界的上下间距 | 增大 → 菜单项上下留白更多 |

### 菜单项（`.context-menu-item`）

```css
.context-menu-item {
  padding: 8px 16px;
  font-size: 13px;
  gap: 6px;           /* 图标与文字间距 */
  transition: background 0.12s;
}
.context-menu-item:hover {
  background: color-mix(in srgb, var(--accent) 12%, transparent);
}
```

| 属性 | 含义 | 修改指导 |
|------|------|----------|
| `padding: 8px 16px` | 菜单项内边距 | 增大 → 菜单项更高更宽；减小 → 更紧凑 |
| `font-size: 13px` | 菜单文字大小 | 与全局 UI 字号保持一致 |
| `gap: 6px` | 图标与文字间距 | 增大 → 图标与文字间隔更宽 |
| `transition: background 0.12s` | hover 背景色的过渡时长 | 增大（如 0.2s）→ 过渡更平滑但略显拖沓；减小 → 更干脆 |
| `hover background: … 12%` | hover 时 accent 颜色的混合比例 | 增大 → hover 背景色更明显 |

### 弹出动画（Transition）

使用 Vue 内置 `<Transition name="menu-pop">`，定义四个 CSS 类：

```css
/* 进入动画：120ms 缓出 */
.menu-pop-enter-active {
  transition: opacity 0.12s ease-out, transform 0.12s ease-out;
}

/* 离开动画：80ms 缓入（比进入快，符合直觉） */
.menu-pop-leave-active {
  transition: opacity 0.08s ease-in, transform 0.08s ease-in;
}

/* 进入起始状态：透明 + 缩小到 92% */
.menu-pop-enter-from {
  opacity: 0;
  transform: scale(0.92);
}

/* 离开结束状态：透明 + 缩小到 92% */
.menu-pop-leave-to {
  opacity: 0;
  transform: scale(0.92);
}
```

#### 动画参数总表

| 类名 | 触发时机 | 默认值 | 修改指导 |
|------|----------|--------|----------|
| `.menu-pop-enter-active` | 元素插入 DOM 时 | 120ms ease-out | 增大（如 200ms）→ 进入更优雅但稍慢；减小（如 60ms）→ 更干脆 |
| `.menu-pop-leave-active` | 元素移除 DOM 时 | 80ms ease-in | 离开应快于进入，符合 UI 直觉；建议保持 ≤ enter 时长 |
| `.menu-pop-enter-from` | 进入动画第一帧 | `scale(0.92)` + `opacity: 0` | 调大 scale（如 0.96）→ 弹入幅度更小；调小 → 弹出感更强 |
| `.menu-pop-leave-to` | 离开动画最后一帧 | `scale(0.92)` + `opacity: 0` | 建议与 enter-from 一致，避免视觉跳跃 |

#### 动画设计原则

1. **方向一致性**：进入和离开使用相同的 `scale` 和 `opacity` 终始值，避免闪烁
2. **时长不对称**：进入（120ms）> 离开（80ms），用户感知更自然
3. **轴心**：`transform-origin: top left` 使缩放以菜单左上角为锚点，对齐光标位置
4. **缓动函数**：进入用 `ease-out`（先快后慢），离开用 `ease-in`（先慢后快），符合物理运动直觉

若需完全禁用动画，将上述四个类的 `transition` 和 `transform` 移除或设置为 `none`。也可仅保留 `opacity` 过渡实现纯淡入淡出效果。

---

## 扩展指南

### 添加新菜单项

在 `ChatWindow.vue` 的 `ctxMenuItems` 数组中新增项即可：

```typescript
const ctxMenuItems: ContextMenuItem[] = [
  { label: '引用', action: 'cite', icon: '💬' },
  { label: '复制', action: 'copy', icon: '📋' },     // 新增
  { label: '分享', action: 'share', icon: '🔗' },    // 新增
]
```

在 `handleContextMenuSelect` 中添加对应分支：

```typescript
function handleContextMenuSelect(action: string) {
  switch (action) {
    case 'cite':
      // 现有逻辑
      break
    case 'copy':
      // await navigator.clipboard.writeText(pendingCitation.value.text)
      break
    case 'share':
      // 分享逻辑
      break
  }
  closeContextMenu()
}
```

### 添加自定义菜单项属性

扩展 `ContextMenuItem` 接口（在 `ContextMenu.vue` 中）：

```typescript
export interface ContextMenuItem {
  label: string
  action: string
  icon?: string
  disabled?: boolean       // 新增
  divider?: boolean        // 新增：上方显示分割线
  shortcut?: string        // 新增：快捷键提示，如 "Ctrl+C"
}
```

`ContextMenu.vue` 模板对应扩展：

```html
<template v-for="item in items" :key="item.action">
  <div v-if="item.divider" class="context-menu-divider"></div>
  <button
    v-else
    class="context-menu-item"
    :disabled="item.disabled"
    @click="select(item.action)"
  >
    <span v-if="item.icon" class="context-menu-icon">{{ item.icon }}</span>
    <span>{{ item.label }}</span>
    <span v-if="item.shortcut" class="context-menu-shortcut">{{ item.shortcut }}</span>
  </button>
</template>
```

### 按气泡类型显示不同菜单

在 `onBubbleContextMenu` 中根据 `sourceType` 动态构造菜单项：

```typescript
function onBubbleContextMenu(event, sourceType, fullText, sourceLabel) {
  // ... 现有文本检测逻辑 ...

  // 动态构建菜单
  const items: ContextMenuItem[] = [{ label: '引用', action: 'cite' }]

  if (sourceType === 'tool_result') {
    items.push({ label: '查看原始输出', action: 'view_raw' })
  }
  if (sourceType === 'assistant_message') {
    items.push({ label: '复制回复', action: 'copy' })
  }

  ctxMenuItems.value = items
  // ... 显示菜单 ...
}
```

注意：`ctxMenuItems` 需要从 `const` 改为 `ref`：

```typescript
const ctxMenuItems = ref<ContextMenuItem[]>([{ label: '引用', action: 'cite', icon: '💬' }])
```

### 引用功能自身可扩展

- **引用多条合并**：当前多条引用分别以 `[引用: text]` 发送，可改为更结构化的格式（如 JSON block）
- **引用位置锚点**：记录引用的 turnId + eventIndex，允许 AI 回复时回溯到原文
- **跨会话引用**：持久化引用数据，允许在新会话中引用历史消息
