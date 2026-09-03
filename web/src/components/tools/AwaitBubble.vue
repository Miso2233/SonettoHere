<template>
  <BubbleChrome :tool-call="toolCall">
    <div v-if="toolCall.status === 'running' || toolCall.status === 'awaiting_user'" class="await-waiting">
      <span class="spinner"></span>
      <span>{{ waitingText }}</span>
      <span v-if="timeoutHint" class="await-hint">{{ timeoutHint }}</span>
    </div>
    <div v-else-if="toolCall.status === 'error'" class="await-error">
      {{ toolCall.output || '等待后台任务失败' }}
    </div>
    <div v-else class="await-result">
      <div class="await-result-title">后台任务 #{{ displayIndex }} 返回结果</div>
      <pre class="await-result-block">{{ resultText }}</pre>
    </div>
  </BubbleChrome>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'

const props = defineProps<{ toolCall: ToolCall }>()

const parsedIndex = computed((): number | null => {
  if (typeof props.toolCall.awaitIndex === 'number') return props.toolCall.awaitIndex
  let parsed: unknown = null
  try {
    parsed = JSON.parse(props.toolCall.input)
  } catch {
    return null
  }
  if (parsed !== null && typeof parsed === 'object' && 'index' in parsed) {
    const idx: unknown = (parsed as Record<string, unknown>)['index']
    if (typeof idx === 'number' && idx > 0) return idx
  }
  return null
})

const displayIndex = computed((): string => (parsedIndex.value === null ? '?' : String(parsedIndex.value)))

const waitingText = computed((): string =>
  parsedIndex.value !== null ? `等待后台任务 #${parsedIndex.value} 完成...` : '等待后台任务完成...'
)

const timeoutHint = computed((): string => {
  if (props.toolCall.status !== 'done') return ''
  const elapsed = props.toolCall.elapsed
  return elapsed !== null && elapsed > 0 ? `（已等待 ${elapsed}s，任务仍在运行）` : ''
})

const resultText = computed((): string => props.toolCall.output ?? '')
</script>
