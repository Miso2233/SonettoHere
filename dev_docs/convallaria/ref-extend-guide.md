# 引用系统扩展指南

## 概述

引用系统采用 **可辨识联合（Discriminated Union）** 设计，添加新类型的引用只需在类型层 + 渲染层 + 触发层各加一段代码，无需修改已有逻辑。

当前支持的类型：

| type | 含义 | 界面触发方式 |
|------|------|--------------|
| `file` | 本地文件 | 文件选择器 |
| `folder` | 本地文件夹 | 文件夹选择器 |
| `cite` | 消息文本引用 | 右键菜单「引用」 |
| `web_link` | 网页链接 | 「加入链接」按钮 / 粘贴 URL |
| `skill` | Anthropic Skill | `@` 触发补全面板 |
| `tool` | 内置工具 | `#` 触发补全面板 |

## 数据流

```
触发源 → ChatInput.addRef(ref) → refs[]
                                  ↓
                            handleSend()
                                  ↓
                     useChat.send(text, refs, ...)
                          ↓               ↓
                   ChatTurn.refs      buildFlatMessage()
                   (前端展示)          (WebSocket 序列化)
```

## 扩展步骤

以假设新增 `code_snippet` 类型为例。

### 1. 定义类型（`web/src/utils/references.ts`）

```typescript
/** 代码片段引用 */
export interface CodeSnippetRef {
  type: 'code_snippet'
  label: string
  language: string
  code: string
}
```

在 `ParsedRef` 联合中添加：

```typescript
export type ParsedRef = FileRef | FolderRef | CiteRef | WebLinkRef | SkillRef | ToolRef | CodeSnippetRef
```

### 2. 注册渲染配置（`web/src/utils/references.ts`）

在 `REF_CHIP_CONFIG` 中添加：

```typescript
export const REF_CHIP_CONFIG: Record<string, RefChipConfig> = {
  // ... 现有 ...
  code_snippet: {
    icon: 'code',           // Icon.vue 中注册的图标名
    tooltip: (r: ParsedRef) => `[${(r as CodeSnippetRef).language}] ${(r as CodeSnippetRef).label}`,
  },
}
```

### 3. 注册图标（`web/src/components/Icon.vue`）

```typescript
import codeRaw from '@/assets/icons/chat-input/code.svg?raw'

const svgContents: Record<string, string> = {
  // ... 现有 ...
  code: codeRaw,
}
```

SVG 图标文件存入 `web/src/assets/icons/chat-input/`，使用 `fill="none"` + `stroke="currentColor"` 线稿风格，`stroke-width="1.5"`。

### 4. 添加触发方式

根据引用类型的来源，选择合适的触发方式：

| 来源 | 触发方式 | 参考实现 |
|------|----------|----------|
| 用户输入 | 补全面板（`#`/`@` 等） | `ChatInput.vue` 中 `watch(text)` + `SkillAutocomplete` |
| 用户粘贴 | `@paste` 检测 | `onPaste()` 函数 |
| 右键菜单 | `ContextMenu` | `ChatWindow.vue` 中 `handleContextMenuSelect` |
| 文件选择 | 菜单按钮 | `pickFile()` / `pickFolder()` / `startLinkInput()` |
| 自定义 UI | 独立输入条 | `showLinkInput` + `link-input-bar` 模板 |

调用 `addRef()` 注入引用：

```typescript
// 在任何组件中（通过 defineExpose 暴露）
chatInputRef.value?.addRef({
  type: 'code_snippet',
  label: 'hello.py',
  language: 'python',
  code: 'print("hello")',
})
```

### 5. 序列化（自动）

`buildFlatMessage()` 使用 `JSON.stringify(refs)`，新类型的字段会自动包含在 `__refs__[...]__/refs__` 块中。

```json
__refs__[{"type":"code_snippet","label":"hello.py","language":"python","code":"print(\"hello\")"}]__/refs__
```

无需修改 `parseReferences()`。

### 6. 展示（自动）

`MessageBubble.vue` 遍历 `turn.refs` 渲染为 `<ReferenceChip>`。`ReferenceChip` 通过 `REF_CHIP_CONFIG[r.type]` 查找图标和 tooltip，新类型即插即用。

### 7. 可选：后端 API

如果新引用类型需要后端数据支持（如技能列表、工具列表），在 `api/routes/skills.py` 中添加端点：

```python
@router.get("/code-snippets")
async def list_code_snippets():
    return {"snippets": [...]}
```

前端通过 `web/src/api/index.ts` 中 `api.listCodeSnippets()` 调用。

## 验证清单

- [ ] 类型定义加入 `ParsedRef` 联合，TypeScript 编译无错误
- [ ] `REF_CHIP_CONFIG` 注册了 icon 和 tooltip
- [ ] Icon 在 `Icon.vue` 中注册且 SVG 文件存在
- [ ] 触发方式能正确调用 `addRef()`
- [ ] 发送时 `buildFlatMessage` 输出的 JSON 包含新类型字段
- [ ] 消息气泡中 `ReferenceChip` 正确显示图标和 tooltip
- [ ] 旧 localStorage 数据通过 `migrateLegacyTurn` 兼容（只检查 `turn.refs` 是否为数组）
