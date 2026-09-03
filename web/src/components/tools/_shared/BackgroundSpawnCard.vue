<template>
  <BubbleChrome :tool-call="toolCall">
    <div class="bg-spawn">
      <div class="bg-spawn-head">
        <span class="bg-spawn-icon">🚀</span>
        <span class="bg-spawn-title">已转入后台运行</span>
        <span class="bg-spawn-index">#{{ index }}</span>
      </div>
      <div class="bg-spawn-meta">Agent 稍后会通过 await_background 取回结果，期间可继续其他工作</div>

      <div v-if="argRows.length" class="bg-spawn-args">
        <div class="bg-spawn-row" v-for="row in argRows" :key="row.key">
          <span class="bg-spawn-key">{{ row.key }}</span>
          <span class="bg-spawn-value">{{ row.value }}</span>
        </div>
      </div>

      <div v-if="previewText" class="bg-spawn-preview" :class="toolCall.background?.status">
        <span class="bg-spawn-preview-label">{{ previewLabel }}</span>
        <span class="bg-spawn-preview-text">{{ previewText }}</span>
      </div>
    </div>
  </BubbleChrome>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ToolCall } from '@/types'
import BubbleChrome from './BubbleChrome.vue'

const props = defineProps<{ toolCall: ToolCall }>()

const index = computed(() => props.toolCall.background?.index ?? '?')

/** 入参 KV 行：优先后端元数据，降级解析气泡 input */
const argRows = computed<{ key: string; value: string }[]>(() => {
  let args: unknown = props.toolCall.background?.args
  if (!args || typeof args !== 'object') {
    args = parseLoose(props.toolCall.input)
  }
  if (!args || typeof args !== 'object') return []
  return Object.entries(args as Record<string, unknown>)
    .filter(([key]) => key !== 'background')
    .slice(0, 8)
    .map(([key, value]) => ({
      key,
      value: summarize(value),
    }))
})

function parseLoose(raw: string): unknown {
  const candidates = [
    raw,
    raw.replace(/\bTrue\b/g, 'true').replace(/\bFalse\b/g, 'false').replace(/\bNone\b/g, 'null'),
  ]
  for (const candidate of candidates) {
    try {
      return JSON.parse(candidate)
    } catch { /* try next */ }
  }
  return null
}

function summarize(value: unknown): string {
  if (typeof value === 'string') {
    const oneLine = value.replace(/\s+/g, ' ').trim()
    return oneLine.length > 120 ? oneLine.slice(0, 120) + '…' : oneLine
  }
  const json = JSON.stringify(value)
  return json !== undefined && json.length > 120 ? json.slice(0, 120) + '…' : String(json ?? value)
}

const bgStatus = computed(() => props.toolCall.background?.status ?? 'running')

const previewText = computed(() => {
  const preview = props.toolCall.background?.resultPreview
  if (!preview || bgStatus.value === 'running') return ''
  const oneLine = preview.replace(/\s+/g, ' ').trim()
  return oneLine.length > 200 ? oneLine.slice(0, 200) + '…' : oneLine
})

const previewLabel = computed(() =>
  bgStatus.value === 'completed' ? '✓ 已完成' : '✗ 失败'
)
</script>
