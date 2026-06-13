import { Marked } from 'marked'
import markedKatex from 'marked-katex-extension'

const marked = new Marked({
  breaks: true,
  gfm: true,
})
marked.use(markedKatex())

export function renderMarkdown(content: string): string {
  if (!content) return ''
  return marked.parse(content) as string
}

/**
 * 检测 Markdown 原文是否包含需要沙箱隔离的原始 HTML/JS/CSS。
 * 跳过围栏代码块内的内容，避免误判示例代码。
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
  const lines = markdown.split('\n')
  for (const line of lines) {
    const trimmed = line.trimStart()
    // 切换围栏代码块状态
    if (trimmed.startsWith('```')) {
      inCodeBlock = !inCodeBlock
      continue
    }
    if (inCodeBlock) continue

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
