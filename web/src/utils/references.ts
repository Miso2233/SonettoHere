/** 文件引用 */
export interface FileRef {
  type: 'file'
  label: string
  path: string
  blocked?: boolean
  blockedReason?: string
}

/** 文件夹引用 */
export interface FolderRef {
  type: 'folder'
  label: string
  path: string
  blocked?: boolean
  blockedReason?: string
}

/** 文本引用（右键引用已有消息内容） */
export interface CiteRef {
  type: 'cite'
  label: string
  text: string
}

/** 网页链接引用（保留供后续使用） */
export interface WebLinkRef {
  type: 'web_link'
  label: string
  url: string
  domain: string
}

/** Anthropic Skill 引用 */
export interface SkillRef {
  type: 'skill'
  label: string
  name: string
}

/** 内置工具引用 */
export interface ToolRef {
  type: 'tool'
  label: string
  name: string
}

/** 宏引用 */
export interface MacroRef {
  type: 'macro'
  label: string
  name: string
}

export type ParsedRef = FileRef | FolderRef | CiteRef | WebLinkRef | SkillRef | ToolRef | MacroRef

/**
 * 引用 chip 渲染配置，每种 type 自注册 icon 名与 tooltip 函数。
 * 添加新类型只需在此增加一条记录，ReferenceChip 组件无需改动。
 */
export interface RefChipConfig {
  icon: string
  tooltip: (ref: ParsedRef) => string
}

export const REF_CHIP_CONFIG: Record<string, RefChipConfig> = {
  file: {
    icon: 'file',
    tooltip: (r: ParsedRef) => (r as FileRef).path,
  },
  folder: {
    icon: 'menu-folder',
    tooltip: (r: ParsedRef) => (r as FolderRef).path,
  },
  cite: {
    icon: 'cite-speech',
    tooltip: (r: ParsedRef) => (r as CiteRef).text,
  },
  web_link: {
    icon: 'link',
    tooltip: (r: ParsedRef) => (r as WebLinkRef).url,
  },
  skill: {
    icon: 'sparkles',
    tooltip: (r: ParsedRef) => `技能: ${(r as SkillRef).name}`,
  },
  tool: {
    icon: 'tool',
    tooltip: (r: ParsedRef) => `工具: ${(r as ToolRef).name}`,
  },
  macro: {
    icon: 'sparkles',
    tooltip: (r: ParsedRef) => `宏: ${(r as MacroRef).name}`,
  },
}

export interface ParseResult {
  cleanText: string
  refs: ParsedRef[]
}

const REFS_START = '__refs__'
const REFS_END = '__/refs__'

export function parseReferences(text: string): ParseResult {
  const startIdx = text.lastIndexOf(REFS_START)
  if (startIdx === -1) {
    return { cleanText: text, refs: [] }
  }

  const endIdx = text.indexOf(REFS_END, startIdx + REFS_START.length)
  if (endIdx === -1) {
    return { cleanText: text, refs: [] }
  }

  const json = text.slice(startIdx + REFS_START.length, endIdx)
  let refs: ParsedRef[]
  try {
    refs = JSON.parse(json)
    if (!Array.isArray(refs)) {
      return { cleanText: text, refs: [] }
    }
  } catch {
    return { cleanText: text, refs: [] }
  }

  const before = text.slice(0, startIdx)
  const cleanText = before.replace(/\n{3,}/g, '\n\n').trim()

  return { cleanText, refs }
}

export function buildRefsBlock(refs: ParsedRef[]): string {
  if (refs.length === 0) return ''
  return `\n\n${REFS_START}${JSON.stringify(refs)}${REFS_END}`
}

/** 构造前端自动追加的 ISO 时间尾缀，如（2026-06-10 Wed 14:30） */
export function buildTimestamp(): string {
  const now = new Date()
  const y = now.getFullYear()
  const mo = String(now.getMonth() + 1).padStart(2, '0')
  const d = String(now.getDate()).padStart(2, '0')
  const hh = String(now.getHours()).padStart(2, '0')
  const mm = String(now.getMinutes()).padStart(2, '0')
  const weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
  const wd = weekdays[now.getDay()]
  return `（${y}-${mo}-${d} ${wd} ${hh}:${mm}）`
}

/** 构建 WebSocket 发送用的平面字符串（结构化 → 序列化） */
export function buildFlatMessage(text: string, timestamp: string, refs: ParsedRef[]): string {
  const base = text + timestamp
  if (refs.length === 0) return base
  return base + buildRefsBlock(refs)
}
