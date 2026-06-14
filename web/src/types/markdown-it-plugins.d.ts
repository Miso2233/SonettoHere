declare module 'markdown-it-texmath' {
  import type MarkdownIt from 'markdown-it'
  import type { KatexOptions } from 'katex'

  interface TexmathOptions {
    engine?: typeof import('katex')
    delimiters?: Array<'dollars' | 'parentheses' | 'brackets' | 'beg_end'>
    allow_escape?: boolean
    katexOptions?: KatexOptions
    macros?: Record<string, string>
  }

  const texmath: (md: MarkdownIt, options?: TexmathOptions) => void
  export default texmath
}

declare module 'markdown-it-task-lists' {
  import type MarkdownIt from 'markdown-it'

  interface TaskListsOptions {
    enabled?: boolean
    label?: boolean
    labelAfter?: boolean
  }

  const taskLists: (md: MarkdownIt, options?: TaskListsOptions) => void
  export default taskLists
}
