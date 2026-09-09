<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 执行中 -->
    <div v-if="toolCall.status === 'running'" class="ms-running">正在检索长期记忆…</div>

    <!-- 出错 -->
    <div v-else-if="toolCall.status === 'error'" class="ms-error">
      {{ toolCall.output || '检索失败' }}
    </div>

    <!-- 完成 -->
    <template v-else-if="toolCall.status === 'done'">
      <div v-if="hasData" class="ms">
        <!-- 查询输入栏：主题 + 检索关键词 -->
        <div class="ms-bar">
          <div class="ms-query">
            <span v-if="themeText" class="ms-theme">{{ themeText }}</span>
            <code class="ms-regex">{{ regexText || '—' }}</code>
          </div>
          <span class="ms-stats">
            命中 {{ matchedTotal }} · 关联 {{ relatedTotal }}
            <span v-if="truncated" class="ms-trunc">· 部分截断</span>
          </span>
        </div>

        <div v-if="matched.length" class="ms-block">
          <div class="ms-label">命中记忆</div>
          <div v-for="(m, i) in matched" :key="`m-${m.id ?? i}`" class="ms-item">
            <div class="ms-item-head">
              <span class="ms-theme">{{ m.theme }}</span>
              <span class="ms-item-id">{{ m.id }}</span>
            </div>
            <p class="ms-desc">{{ m.description }}</p>
          </div>
        </div>

        <div v-if="related.length" class="ms-block">
          <div class="ms-label">关联记忆</div>
          <div v-for="(r, i) in related" :key="`r-${r.id ?? i}`" class="ms-item">
            <div class="ms-item-head">
              <span class="ms-theme">{{ r.theme }}</span>
              <span v-if="r.depth" class="ms-depth">第 {{ r.depth }} 级</span>
              <span class="ms-item-id">{{ r.id }}</span>
            </div>
            <p class="ms-desc">{{ r.description }}</p>
          </div>
        </div>

        <div v-if="!hasResults" class="ms-empty">{{ summary || '未检索到相关记忆' }}</div>
      </div>

      <div v-else-if="toolCall.output" class="ms-raw">{{ toolCall.output }}</div>
    </template>

    <!-- 未知状态兜底 -->
    <div v-else-if="toolCall.output" class="ms-raw">{{ toolCall.output }}</div>
  </BubbleChrome>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'

interface MemEntry {
  id?: string
  theme?: string
  description?: string
  depth?: number
}

interface MemorySearchData {
  summary?: string
  regex?: string
  theme?: string | null
  matched_total?: number
  related_total?: number
  truncated?: boolean
  matched?: MemEntry[]
  related?: MemEntry[]
}

const props = defineProps<{ toolCall: ToolCall }>()
defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

/** 从 toolData 取结构化数据；缺失时降级解析完整 output JSON */
const data = computed<MemorySearchData>(() => {
  if (props.toolCall.toolData) {
    return props.toolCall.toolData as MemorySearchData
  }
  if (props.toolCall.output) {
    try {
      const p = JSON.parse(props.toolCall.output) as { data?: MemorySearchData }
      if (p?.data) return p.data
    } catch { /* ignore */ }
  }
  return {}
})

/** 兜底：从原始 tool 入参（str(dict) 或 JSON）里抽取 regex/theme，用于展示查询输入 */
function parseInputArgs(raw: string | null): { regex?: string; theme?: string | null } {
  if (!raw) return {}
  try {
    const o = JSON.parse(raw) as { regex?: string; theme?: string | null }
    return { regex: o?.regex, theme: o?.theme }
  } catch { /* not JSON */ }
  const pick = (key: string): string | undefined => {
    const m = raw.match(
      new RegExp(`['"]?${key}['"]?\\s*:\\s*(?:'([^']*)'|"([^"]*)"|([^,}\\s]+))`)
    )
    return m ? (m[1] ?? m[2] ?? m[3]) : undefined
  }
  const theme = pick('theme')
  return { regex: pick('regex'), theme: theme || null }
}

const inputArgs = computed(() => parseInputArgs(props.toolCall.input ?? null))

const regexText = computed<string>(() =>
  typeof data.value.regex === 'string' && data.value.regex ? data.value.regex : (inputArgs.value.regex || '')
)
const themeText = computed<string>(() =>
  typeof data.value.theme === 'string' && data.value.theme ? data.value.theme : (inputArgs.value.theme || '')
)

const matched = computed<MemEntry[]>(() =>
  Array.isArray(data.value.matched) ? data.value.matched : []
)
const related = computed<MemEntry[]>(() =>
  Array.isArray(data.value.related) ? data.value.related : []
)
const hasData = computed(() => Object.keys(data.value).length > 0)
const hasResults = computed(() => matched.value.length > 0 || related.value.length > 0)
const matchedTotal = computed(() =>
  typeof data.value.matched_total === 'number' ? data.value.matched_total : matched.value.length
)
const relatedTotal = computed(() =>
  typeof data.value.related_total === 'number' ? data.value.related_total : related.value.length
)
const summary = computed(() =>
  typeof data.value.summary === 'string' && data.value.summary ? data.value.summary : ''
)
const truncated = computed(() => data.value.truncated === true)
</script>

<style scoped>
/* ── 黑白撞色极简（与 Tavily 系列一致）── */
.ms-running {
  padding: 10px 0;
  font-size: 13px;
  color: #888;
}
.ms-error {
  padding: 8px 0;
  font-size: 13px;
  color: #666;
}

.ms {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 4px 0;
}

/* ── 顶部查询栏 ── */
.ms-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  background: #f5f5f5;
  border-radius: 6px;
  flex-wrap: wrap;
}
.ms-query {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}
.ms-regex {
  font-size: 13px;
  font-weight: 600;
  color: #000;
  font-family: 'SF Mono', 'Consolas', monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.ms-stats {
  font-size: 12px;
  font-weight: 700;
  color: #000;
  white-space: nowrap;
  flex-shrink: 0;
}
.ms-trunc {
  font-size: 10px;
  font-weight: 600;
  color: #555;
  margin-left: 2px;
}

/* ── 主题描边标签 ── */
.ms-theme {
  flex-shrink: 0;
  font-size: 10px;
  font-weight: 700;
  padding: 1px 6px;
  border: 1px solid #ccc;
  border-radius: 2px;
  color: #555;
  letter-spacing: .5px;
}

/* ── 分组 ── */
.ms-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ms-label {
  font-size: 10px;
  font-weight: 700;
  color: #666;
  letter-spacing: .8px;
  text-transform: uppercase;
  padding: 0 2px;
}

/* ── 条目卡片 ── */
.ms-item {
  padding: 10px 12px;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  transition: border-color .15s;
}
.ms-item:hover { border-color: #000; }

.ms-item-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.ms-depth {
  font-size: 10px;
  color: #888;
}
.ms-item-id {
  font-size: 10px;
  color: #bbb;
  margin-left: auto;
  font-family: 'SF Mono', 'Consolas', monospace;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ms-desc {
  font-size: 13px;
  color: #222;
  line-height: 1.6;
  margin: 6px 0 0;
  word-break: break-word;
}

/* ── 无结果 ── */
.ms-empty {
  text-align: center;
  padding: 20px 16px 4px;
  color: #999;
  font-size: 13px;
}

/* ── 降级 ── */
.ms-raw {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  color: #333;
  white-space: pre-wrap;
  word-break: break-word;
  padding: 8px 12px;
  background: #fafafa;
  border-radius: 4px;
}
</style>
