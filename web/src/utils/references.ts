export interface ParsedRef {
  type: 'file' | 'cite'
  label: string
  path?: string
  text?: string
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
