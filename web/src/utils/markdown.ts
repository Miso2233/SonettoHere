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
