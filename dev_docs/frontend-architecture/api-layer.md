# API 请求层 — `api/` + `utils/`

## API 封装 (`api/index.ts`)

所有 HTTP 请求通过 `api` 单体对象封装，统一管理请求头、认证 Token 和错误处理。

### 请求流程

```typescript
async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['X-Sonetto-Token'] = token          // 认证 Token
  const res = await fetch(`${BASE}${url}`, { headers, ...options })
  if (!res.ok) {                                          // 统一错误处理
    let detail = `API ${url} 返回 ${res.status}`
    try { const body = await res.json(); detail += `: ${body.detail}` } catch { }
    throw new Error(detail)
  }
  return res.json()                                       // 自动 JSON 解析
}
```

### Token 注入方式

Token 在 Vite 构建时从 `config/auth_token.yaml` 读取，通过 `define` 选项注入：

```typescript
// vite.config.ts — 编译期注入
define: { __API_TOKEN__: JSON.stringify(loadApiToken()) }
```

这意味着修改 Token 后需重新构建前端，Token 嵌入在 JS 包中。

### API 方法分类

| 类别 | 方法数 | 前缀 |
|---|---|---|
| 会话管理 | 8 个 | `createSession` / `listSessions` / `getSession` / `deleteSession` / … |
| 提供商管理 | 10 个 | `listProviders` / `getProvider` / `createProvider` / `updateProvider` / `deleteProvider` / `testConnection` / `discoverModels` / … |
| 记忆 | 3 个 | `getNarrative` / `getMoment` / `getMemories` |
| 系统 | 3 个 | `health` / `restart` / `getDeepSeekBalance` |
| 工具配置 | 6 个 | `listTools` / `listSkills` / `listMacros` |
| 路径白名单 | 4 个 | `listWhitelist` / `addWhitelistEntry` / `updateWhitelistEntry` / `deleteWhitelistEntry` |
| 拒止锚 | 3 个 | `listBlockers` / `addBlocker` / `deleteBlocker` |
| 环境变量 | 3 个 | `listEnvVars` / `updateEnvVar` / `batchUpdateEnvVars` |
| 人设 | 2 个 | `getPersona` / `updatePersona` |
| 固定会话 | 3 个 | `constifySession` / `unconstifySession` / `generateSessionTitle` |
| 文件 | 3 个 | `selectFile` / `selectFolder` / `getImageBlobUrl` |
| 安全性 | 1 个 | `checkPathBlocked` |
| 新闻 | 1 个 | `listNews` |

## 工具函数 (`utils/`)

| 文件 | 核心导出 | 用途 |
|---|---|---|
| `markdown.ts` | `renderMarkdown(content)` , `contentNeedsIsolation(content)` | markdown-it 渲染 + HTML 安全检测 |
| `references.ts` | `parseReferences(text)` , `buildFlatMessage(text, timestamp, refs)` , `buildTimestamp()` | 引用解析与消息构建 |
| `python-highlight.ts` | (Python 语法高亮配置) | CodeMirror Python 语法高亮 |

### markdown.ts — 渲染引擎

使用 **markdown-it** + 两个插件的渲染管线：

```typescript
const md = new MarkdownIt({ html: true, breaks: true, linkify: true })
  .use(taskLists, { enabled: true })            // GFM 任务列表 - [x]
  .use(texmath, { engine: katex, delimiters: ['dollars', 'parentheses', 'brackets'] })
  // 自定义 fence 渲染器：```html 输出原始 HTML
  md.renderer.rules.fence = (tokens, idx) => {
    if (lang === 'html') return token.content   // 直接插入 HTML
    return defaultFence(tokens, idx, ...)        // 默认转义显示
  }
```

### references.ts — 引用系统

```typescript
// 解析用户消息中的引用标记
parseReferences(
  '查看图片 ![本地](file:///C:/img.png) 和文档 [[cite:Hello World]]'
)
// → { cleanText: '查看图片 和文档', refs: [{ type: 'file', path: '…' }, { type: 'cite', text: 'Hello World' }] }

// 构建扁平消息（移除引用标记后的纯文本，供后端 LLM 使用）
buildFlatMessage(text, timestamp, refs)
// → "# 2026-07-17 14:30 … 查看图片 和文档【引用 2 条】"
```

引用类型：
| type | 格式 | 来源 |
|---|---|---|
| `file` | `![label](file:///path)` | 文件选择器 |
| `link` | `[label](URL)` | 链接输入栏 |
| `cite` | `[[cite:selected text]]` | 右键菜单"引用" |
