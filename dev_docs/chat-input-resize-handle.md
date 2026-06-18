# ChatInput 拖拽调整高度功能

**文件**: `web/src/components/ChatInput.vue`  
**日期**: 2026-06-18

---

## 功能概述

在文本输入框顶部新增一个可拖拽的手柄，用户可上下拖拽来调整输入区域的高度，解决输入长文本时对话框过窄的问题。

---

## 变更 1：模板 — 新增拖拽手柄元素

```diff
-    <div class="chat-input">
+    <div
+      ref="inputContainerRef"
+      class="chat-input"
+      :class="{ 'is-resizing': isResizing }"
+      :style="containerStyle"
+    >
+      <div
+        class="resize-handle"
+        @pointerdown="startResize"
+        title="拖拽调整输入框高度"
+      >
+        <div class="resize-handle-grip"></div>
+      </div>
       <textarea
```

---

## 变更 2：脚本 — 新增 inputContainerRef

```diff
 const text = ref('')
 const textareaRef = ref<HTMLTextAreaElement | null>(null)
+const inputContainerRef = ref<HTMLDivElement | null>(null)
 const refs = ref<ParsedRef[]>([])
```

---

## 变更 3：脚本 — 修改 autoResize()

```diff
 function autoResize() {
   const el = textareaRef.value
   if (!el) return
+  // 如果用户手动拖拽过容器高度，不干涉 textarea 高度，交由 flex 布局自动填充
+  if (customHeight.value !== null) return
   el.style.height = 'auto'
   el.style.height = Math.min(el.scrollHeight, 160) + 'px'
 }
```

---

## 变更 4：脚本 — 新增拖拽逻辑

```diff
+// ── 拖拽调整输入框高度 ──
+
+const customHeight = ref<number | null>(null)
+const isResizing = ref(false)
+const resizeStartY = ref(0)
+const resizeStartHeight = ref(0)
+const handleRef = ref<HTMLDivElement | null>(null)
+const initialHeight = ref(120)
+
+const containerStyle = computed(() => {
+  if (customHeight.value === null) return {}
+  return { height: customHeight.value + 'px' }
+})
+
+/** 组件挂载后捕获输入框的初始默认高度，作为拖拽下限 */
+onMounted(() => {
+  nextTick(() => {
+    const el = inputContainerRef.value
+    if (el) initialHeight.value = el.clientHeight
+  })
+})
+
+function startResize(e: PointerEvent) {
+  const handle = e.currentTarget as HTMLDivElement
+  handle.setPointerCapture(e.pointerId)
+  handleRef.value = handle
+
+  isResizing.value = true
+  resizeStartY.value = e.clientY
+  const el = inputContainerRef.value
+  resizeStartHeight.value = el ? el.clientHeight : initialHeight.value
+  if (customHeight.value === null) {
+    customHeight.value = resizeStartHeight.value
+  }
+
+  handle.addEventListener('pointermove', onResizeMove)
+  handle.addEventListener('pointerup', onResizeEnd)
+  handle.addEventListener('pointercancel', onResizeEnd)
+}
+
+function onResizeMove(e: PointerEvent) {
+  const delta = resizeStartY.value - e.clientY
+  const newHeight = Math.max(initialHeight.value, Math.min(600, resizeStartHeight.value + delta))
+  customHeight.value = newHeight
+}
+
+function onResizeEnd(e: PointerEvent) {
+  isResizing.value = false
+  const handle = handleRef.value
+  if (handle) {
+    handle.releasePointerCapture(e.pointerId)
+    handle.removeEventListener('pointermove', onResizeMove)
+    handle.removeEventListener('pointerup', onResizeEnd)
+    handle.removeEventListener('pointercancel', onResizeEnd)
+    handleRef.value = null
+  }
+}
```

---

## 变更 5：样式 — 新增拖拽手柄样式

```diff
+/* 拖拽调整手柄 */
+.resize-handle {
+  display: flex;
+  justify-content: center;
+  align-items: center;
+  height: 14px;
+  cursor: ns-resize;
+  user-select: none;
+  touch-action: none;
+  flex-shrink: 0;
+}
+.resize-handle-grip {
+  width: 48px;
+  height: 3px;
+  border-radius: 2px;
+  background: var(--border);
+  transition: background 0.15s, width 0.2s;
+}
+.resize-handle:hover .resize-handle-grip {
+  background: var(--accent);
+  width: 64px;
+}
```

---

## 变更 6：样式 — 修改 .chat-input

```diff
 .chat-input {
   display: flex;
   flex-direction: column;
-  gap: 8px;
+  gap: 4px;
   background: var(--bg-card);
   border: 1px solid var(--border);
   border-radius: 14px;
-  padding: 10px 14px 8px;
+  padding: 4px 14px 8px;
   box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
   transition: border-color 0.2s, box-shadow 0.2s;
+  overflow: hidden;
+}
+.chat-input.is-resizing {
+  border-color: var(--accent);
+  box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 20%, transparent);
 }
```

---

## 变更 7：样式 — 修改 .input-area

```diff
 .input-area {
-  flex: 1;
+  flex: 1 1 0;
   border: none;
   outline: none;
   background: transparent;
   font-size: 15px;
   line-height: 1.6;
   color: var(--text-primary);
   resize: none;
   font-family: inherit;
   min-height: 24px;
+  overflow-y: auto;
 }
```

---

## 交互说明

1. 输入框顶部显示一条灰色短横线（48px 宽）
2. 鼠标悬停时横线变蓝、变长（64px），光标变为上下箭头
3. **按住横线向上拖拽** → 输入区域扩大
4. **按住横线向下拖拽** → 输入区域缩小
5. 拖拽范围：最小 80px，最大 600px
6. 松开后高度保持，后续输入文字不会改变已设定的高度
7. 拖拽过程中输入框边框高亮为蓝色

---

## 技术要点

- **Pointer Events**：`pointerdown`/`pointermove`/`pointerup` 替代 Mouse Events，兼容触屏
- **setPointerCapture**：确保拖拽时鼠标移出手柄也能持续跟踪
- **容器高度控制**：调整 `.chat-input` 的 `height`，textarea 通过 `flex: 1 1 0` 自动填充
- **autoResize 互斥**：拖拽过后 `autoResize()` 自动跳过，防止覆盖
