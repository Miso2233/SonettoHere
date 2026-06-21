import MarkdownIt from 'markdown-it'
import texmath from 'markdown-it-texmath'
import taskLists from 'markdown-it-task-lists'
import katex from 'katex'

const md = new MarkdownIt({
  html: true,    // 透传原始 HTML（LLM 直接输出交互式 HTML 的关键功能）
  breaks: true,  // \n → <br>，适配聊天场景的换行
  linkify: true, // 自动识别 URL 为可点击链接
})

// GFM 任务列表：- [x] 已完成 / - [ ] 未完成
md.use(taskLists, { enabled: true })

// 数学公式支持：$...$ / $$...$$ / \(...\) / \[...\]
md.use(texmath, {
  engine: katex,
  delimiters: [
    'dollars',     // $...$ 和 $$...$$
    'parentheses', // \(...\)
    'brackets',    // \[...\]
  ],
  allow_escape: true,    // \$ 转义为字面 $ 符号
  katexOptions: {
    throwOnError: false, // 公式渲染失败时降级显示原文，不抛异常
  },
})

// 自定义 fence 渲染器：```html 代码块渲染为实际 HTML，而非源代码显示
const defaultFence = md.renderer.rules.fence

md.renderer.rules.fence = function (tokens, idx, options, env, self) {
  const token = tokens[idx]
  const info = token.info ? token.info.trim() : ''
  const lang = info.split(/\s+/)[0].toLowerCase()

  // ```html 代码块：输出原始内容作为实际 HTML（不包裹 <pre><code>）
  if (lang === 'html') {
    return token.content
  }

  // 其他语言：使用默认渲染（转义后包裹 <pre><code>）
  if (defaultFence) {
    return defaultFence(tokens, idx, options, env, self)
  }
  return self.renderToken(tokens, idx, options)
}

export function renderMarkdown(content: string): string {
  if (!content) return ''
  return md.render(content)
}

/**
 * 检测 Markdown 原文是否包含需要沙箱隔离的原始 HTML/JS/CSS。
 * 跳过非 HTML 围栏代码块内的内容；HTML 代码块（```html）内的内容仍接受沙箱检测。
 *
 * 触发隔离的条件：
 * - `<script>` — JS 脚本（v-html 不执行，iframe 才执行）
 * - `<style>` / `<link rel="stylesheet">` — 全局 CSS（泄漏到气泡外部）
 * - `onXxx="..."` — 内联事件处理器
 * - `href="javascript:..."` — 伪协议 URL
 * - `<iframe>` — 嵌入式框架
 */
export function contentNeedsIsolation(markdown: string): boolean {
  if (!markdown) return false
  let inCodeBlock = false
  let codeBlockLang = ''
  const lines = markdown.split('\n')
  for (const line of lines) {
    const trimmed = line.trimStart()
    // 切换围栏代码块状态，同时记录语言标签
    if (trimmed.startsWith('```')) {
      if (!inCodeBlock) {
        // 进入代码块：提取语言标签（``` 后的第一个词）
        codeBlockLang = trimmed.slice(3).trim().split(/\s+/)[0].toLowerCase()
      } else {
        // 退出代码块：重置语言标签
        codeBlockLang = ''
      }
      inCodeBlock = !inCodeBlock
      continue
    }

    // 跳过非 HTML 代码块内的内容
    if (inCodeBlock && codeBlockLang !== 'html') continue

    // 检查原始 <script> 标签
    if (/<script[\s>/]/i.test(line) || /<\/script>/i.test(line)) return true
    // 检查原始 <style> 标签（全局 CSS 泄漏）
    if (/<style[\s>/]/i.test(line) || /<\/style>/i.test(line)) return true
    // 检查 <link rel="stylesheet">（全局 CSS 泄漏）
    if (/<link[\s>]/i.test(line) && /rel\s*=\s*["']stylesheet["']/i.test(line)) return true
    // 检查内联事件处理器 onXxx="..."
    if (/\son\w+\s*=\s*["']/i.test(line)) return true
    // 检查 javascript: URL
    if (/href\s*=\s*["']\s*javascript:/i.test(line)) return true
    // 检查 <iframe> 嵌入
    if (/<iframe[\s>/]/i.test(line)) return true
  }
  return false
}

/** @deprecated 使用 contentNeedsIsolation */
export const contentHasScripts = contentNeedsIsolation
