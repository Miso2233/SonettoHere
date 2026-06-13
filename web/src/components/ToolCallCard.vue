<template>
  <div class="tool-card" :class="[toolCall.status, { open: isOpen }]">
    <div class="tool-header" @click="toggle" role="button" :aria-expanded="isOpen">
      <span class="tool-icon">
        <span v-if="toolCall.status === 'running'" class="spinner-sm"></span>
        <span v-else-if="toolCall.status === 'done'">&#10003;</span>
        <span v-else>&#10007;</span>
      </span>
      <span class="tool-name">{{ toolCall.name }}</span>
      <span class="tool-elapsed" v-if="toolCall.elapsed !== null">
        {{ toolCall.elapsed }}s
      </span>
    </div>
    <div class="tool-body-wrapper" ref="bodyWrapper">
      <div class="tool-body" ref="bodyInner">
        <!-- 参数 section -->
        <div class="tool-section" v-if="toolCall.input && toolCall.input !== '{}'">
          <div class="tool-section-title">参数</div>
          <template v-if="inputDisplay.type === 'kv'">
            <div class="kv-list">
              <div class="kv-row" v-for="(item, idx) in inputDisplay.pairs" :key="idx">
                <span class="kv-key">{{ item.key }}</span>
                <span class="kv-value" v-if="item.primitive">{{ item.value }}</span>
                <pre class="kv-nested" v-else>{{ item.value }}</pre>
              </div>
            </div>
          </template>
          <RenderMarkdown v-if="inputDisplay.type === 'markdown'" :content="toolCall.input" />
        </div>

        <!-- 结果 section -->
        <div class="tool-section" v-if="toolCall.output">
          <div class="tool-section-title">结果</div>
          <template v-if="outputDisplay.type === 'kv'">
            <div class="kv-list">
              <div class="kv-row" v-for="(item, idx) in outputDisplay.pairs" :key="idx">
                <span class="kv-key">{{ item.key }}</span>
                <span class="kv-value" v-if="item.primitive">{{ item.value }}</span>
                <pre class="kv-nested" v-else>{{ item.value }}</pre>
              </div>
            </div>
          </template>
          <pre v-else-if="outputDisplay.type === 'code'" class="code-block">{{ outputDisplay.raw }}</pre>
          <RenderMarkdown v-if="outputDisplay.type === 'markdown'" :content="toolCall.output || ''" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue'
import type { ToolCall } from '@/types'
import RenderMarkdown from './RenderMarkdown.vue'

const props = defineProps<{ toolCall: ToolCall }>()

const isOpen = ref(false)
const bodyWrapper = ref<HTMLElement | null>(null)
const bodyInner = ref<HTMLElement | null>(null)

// ── JSON KV parsing ──
interface KvPair {
  key: string
  value: string
  primitive: boolean
}

interface KvDisplay {
  type: 'kv'
  pairs: KvPair[]
}

interface CodeDisplay {
  type: 'code'
  raw: string
  lang: string
  lines: number
}

interface MarkdownDisplay {
  type: 'markdown'
}

type SectionDisplay = KvDisplay | CodeDisplay | MarkdownDisplay

function parseJsonKv(raw: string): KvDisplay | null {
  // LangChain may pass Python-style dict strings (True/False/None, single quotes)
  const candidates = [
    raw,
    raw.replace(/\bTrue\b/g, 'true').replace(/\bFalse\b/g, 'false').replace(/\bNone\b/g, 'null'),
    raw.replace(/'/g, '"').replace(/\bTrue\b/g, 'true').replace(/\bFalse\b/g, 'false').replace(/\bNone\b/g, 'null'),
  ]
  for (const candidate of candidates) {
    try {
      const obj = JSON.parse(candidate)
      if (obj === null || typeof obj !== 'object' || Array.isArray(obj)) return null
      const pairs: KvPair[] = Object.entries(obj).map(([key, val]) => {
        const primitive = typeof val !== 'object' || val === null
        return {
          key,
          value: primitive ? String(val) : JSON.stringify(val, null, 2),
          primitive,
        }
      })
      return pairs.length > 0 ? { type: 'kv', pairs } : null
    } catch { /* try next candidate */ }
  }
  return null
}

function detectCodeDisplay(raw: string): CodeDisplay {
  const lines = raw.split('\n').length
  const trimmed = raw.trimStart()
  let lang = 'TEXT'
  if (trimmed.startsWith('{') || trimmed.startsWith('[')) lang = 'JSON'
  else if (trimmed.startsWith('```')) {
    const firstLine = trimmed.split('\n')[0]
    const tag = firstLine.slice(3).trim()
    if (tag) lang = tag.toUpperCase()
  }
  return { type: 'code', raw: raw, lang, lines }
}

const inputDisplay = computed<SectionDisplay>(() => {
  const kv = parseJsonKv(props.toolCall.input)
  if (kv) return kv
  return { type: 'markdown' }
})

const outputDisplay = computed<SectionDisplay>(() => {
  if (!props.toolCall.output) {
    return { type: 'markdown' }
  }
  const kv = parseJsonKv(props.toolCall.output)
  if (kv) return kv
  return detectCodeDisplay(props.toolCall.output)
})

// ── Expand / collapse ──
function toggle() {
  if (props.toolCall.status === 'running') return
  isOpen.value = !isOpen.value
}

watch(isOpen, (open) => {
  if (!bodyWrapper.value) return
  if (open) {
    bodyWrapper.value.style.maxHeight = bodyWrapper.value.scrollHeight + 'px'
  } else {
    bodyWrapper.value.style.maxHeight = bodyWrapper.value.scrollHeight + 'px'
    void bodyWrapper.value.offsetHeight
    bodyWrapper.value.style.maxHeight = '0px'
  }
})

watch(() => props.toolCall.status, (s) => {
  if (s === 'running') {
    isOpen.value = true
  }
})

watch(() => props.toolCall.output, () => {
  nextTick(() => {
    if (isOpen.value && bodyWrapper.value) {
      bodyWrapper.value.style.maxHeight = bodyWrapper.value.scrollHeight + 'px'
    }
  })
})
</script>

<style scoped>
.tool-card {
  margin: 8px 0;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-card);
  box-shadow: var(--shadow);
  overflow: hidden;
}
.tool-card.running {
  border-color: var(--accent-light);
}
.tool-card.error {
  border-color: #fecaca;
}
.tool-header {
  padding: 8px 14px;
  font-size: 13px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}
.tool-icon {
  font-size: 12px;
  width: 16px;
  text-align: center;
}
.spinner-sm {
  display: inline-block;
  width: 10px;
  height: 10px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.tool-name {
  font-weight: 600;
  color: var(--text-primary);
}
.tool-elapsed {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-secondary);
}

/* ── Body ── */
.tool-body-wrapper {
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.3s cubic-bezier(0, 0.3, 0, 1),
              opacity 0.25s ease;
  opacity: 0;
}
.tool-card.open > .tool-body-wrapper {
  opacity: 1;
}
.tool-body {
  border-top: 1px solid var(--border);
  padding: 12px 16px 16px;
}

/* ── Section ── */
.tool-section {
  margin-bottom: 14px;
}
.tool-section:last-child {
  margin-bottom: 0;
}
.tool-section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  padding-bottom: 6px;
  margin-bottom: 10px;
  border-bottom: 1px solid var(--border);
}

/* ── KV list ── */
.kv-list {
  background: var(--bg-primary);
  border-radius: 6px;
  padding: 8px 14px;
}
.kv-row {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 3px 0;
  line-height: 1.6;
}
.kv-key {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  color: var(--text-secondary);
  flex-shrink: 0;
  min-width: 6em;
}
.kv-key::after {
  content: ':';
}
.kv-value {
  font-size: 13px;
  color: var(--text-primary);
  word-break: break-word;
}
.kv-nested {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 11px;
  line-height: 1.5;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  background: var(--bg-secondary);
  padding: 6px 10px;
  border-radius: 4px;
  flex: 1;
  max-height: 120px;
  overflow-y: auto;
}

/* ── Output code block ── */
.code-block {
  margin: 0;
  padding: 10px 14px;
  background: var(--bg-primary);
  border-radius: 6px;
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 200px;
  overflow-y: auto;
}

/* ── Compact markdown overrides inside tool cards ── */
.tool-section :deep(.markdown-body) {
  font-size: 13px;
  line-height: 1.5;
}
.tool-section :deep(.markdown-body pre) {
  font-size: 12px;
  padding: 10px 12px;
  border-radius: 6px;
  margin: 4px 0;
  max-height: 200px;
  overflow-y: auto;
  border-left: 2px solid var(--accent);
}
.tool-section :deep(.markdown-body code) {
  font-size: 12px;
}
.tool-section :deep(.markdown-body) > *:first-child {
  margin-top: 0;
}
.tool-section :deep(.markdown-body) > *:last-child {
  margin-bottom: 0;
}
</style>
