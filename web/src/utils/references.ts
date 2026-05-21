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
