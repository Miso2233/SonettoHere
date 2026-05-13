import { Marked } from 'marked'

const marked = new Marked({
  breaks: true,
  gfm: true,
})

export function renderMarkdown(content: string): string {
  if (!content) return ''
  return marked.parse(content) as string
}
