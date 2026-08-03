/** 提词补全共用工具 — 聊天框与工作坊表单复用同一套过滤/排序逻辑。 */

export type AcMode = 'skill' | 'tool' | 'macro' | null

/** 触发字符 → 补全模式（聊天框使用；工作坊表单按字段直连数据源，不依赖触发字符）。 */
export function detectAcMode(char: string): AcMode {
  if (char === '@') return 'skill'
  if (char === '#') return 'tool'
  if (char === '!' || char === '！') return 'macro'
  return null
}

/** 按 name 前缀优先评分并过滤候选项（与聊天框行为一致）。 */
export function filterAndScore<T extends { name: string }>(
  src: T[],
  filterText: string,
): T[] {
  if (!filterText) return src
  const lower = filterText.toLowerCase()

  const scored: { item: T; score: number; count: number }[] = []
  for (const item of src) {
    const nameLower = item.name.toLowerCase()
    if (!nameLower.includes(lower)) continue
    const prefix = nameLower.startsWith(lower)
    const count = prefix ? 1 : nameLower.split(lower).length - 1
    scored.push({ item, score: prefix ? 4 : 2, count })
  }

  scored.sort((a, b) => {
    if (a.score !== b.score) return b.score - a.score
    if (a.count !== b.count) return b.count - a.count
    return a.item.name.localeCompare(b.item.name)
  })

  return scored.map(s => s.item)
}
