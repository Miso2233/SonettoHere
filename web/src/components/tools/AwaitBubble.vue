<template>
  <!-- 完成态且拿到原工具的结构化数据：直接镜像渲染原工具的专属气泡 -->
  <component
    v-if="mirrorComponent && mirrorData"
    :is="mirrorComponent"
    :tool-call="mirrorCall"
  />
  <BubbleChrome v-else :tool-call="toolCall">
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
import { getBubbleComponent } from './registry'

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

// ── 完成态镜像：复用原工具的专属气泡 ──────────────────────

/** 后端在完成态 tool_data 中标注的原工具名（original_tool） */
const originalTool = computed((): string | null => {
  if (props.toolCall.status !== 'done') return null
  const td = props.toolCall.toolData as { original_tool?: unknown } | undefined
  return typeof td?.original_tool === 'string' && td.original_tool ? td.original_tool : null
})

const mirrorComponent = computed(() =>
  originalTool.value ? getBubbleComponent(originalTool.value) : null
)

/** 剔除镜像标记字段后的原工具结构化数据；为空则回退通用结果展示 */
const mirrorData = computed((): Record<string, unknown> | null => {
  if (!originalTool.value || !props.toolCall.toolData) return null
  const rest: Record<string, unknown> = { ...props.toolCall.toolData }
  delete rest['original_tool']
  delete rest['original_elapsed_s']
  return Object.keys(rest).length > 0 ? rest : null
})

/** 镜像气泡：换成原工具名 + 完成徽章（后台 #N）+ 后台任务真实耗时 */
const mirrorCall = computed((): ToolCall => {
  const originalElapsed = props.toolCall.toolData?.['original_elapsed_s']
  return {
    ...props.toolCall,
    name: originalTool.value ?? props.toolCall.name,
    status: 'done',
    toolData: mirrorData.value ?? undefined,
    elapsed:
      typeof originalElapsed === 'number' ? originalElapsed : props.toolCall.elapsed,
    background:
      parsedIndex.value !== null
        ? { index: parsedIndex.value, status: 'completed' }
        : props.toolCall.background,
  }
})
</script>
