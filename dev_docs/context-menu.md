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
- 半透明 backdrop 层拦截点击关闭 + 阻止原生右键菜单
- `document.addEventListener('keydown')` 监听 Escape 键关闭
- 菜单项通过 `items` prop 传入，组件本身不硬编码菜单内容

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
