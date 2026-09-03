<template>
  <BubbleChrome :tool-call="toolCall">
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>子 Agent 执行中...</span>
    </div>

    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '子 Agent 执行失败' }}
    </div>

    <template v-else-if="toolCall.status === 'done'">
      <div v-if="hasData" class="sa">
        <div class="sa-bar">
          <span class="sa-title">子 Agent</span>
          <span class="sa-id" :title="subSessionId">#{{ subSessionId.slice(0, 8) }}</span>
        </div>

        <div class="sa-answer">
          <div class="sa-answer-label">回答</div>
          <div class="sa-answer-body">{{ answerText }}</div>
        </div>
      </div>

      <div v-else class="sa-raw">{{ fallback }}</div>
    </template>
  </BubbleChrome>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'

const props = defineProps<{ toolCall: ToolCall }>()

const td = computed<Record<string, unknown>>(() => {
  if (props.toolCall.toolData) return props.toolCall.toolData
  if (props.toolCall.output) {
    try {
      const p = JSON.parse(props.toolCall.output) as { data?: Record<string, unknown> }
      if (p?.data) return p.data
    } catch { /* */ }
  }
  return {}
})

const hasData = computed(() => Object.keys(td.value).length > 0)
const subSessionId = computed(() => String(td.value['sub_session_id'] ?? ''))
const answerText = computed(() => {
  const raw = String(td.value['answer'] ?? '')
  return raw.length > 2000 ? raw.slice(0, 2000) + '\n…' : raw
})

const fallback = computed(() =>
  props.toolCall.output
    ? (props.toolCall.output.length > 500 ? props.toolCall.output.slice(0, 500) + '…' : props.toolCall.output)
    : null
)
</script>

<style scoped>
/* ── 布局常量（与 Tavily 系列一致：黑白撞色 + 灰阶） ── */
.bubble-running {
  padding: 12px 0;
  font-size: 13px;
  color: #888;
}
.bubble-error {
  padding: 8px 0;
  font-size: 13px;
  color: #666;
}

.sa {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 4px 0;
}

/* ── 顶栏（同 tavily 查询栏） ── */
.sa-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #f5f5f5;
  border-radius: 6px;
}
.sa-title {
  font-size: 14px;
  font-weight: 600;
  color: #000;
}
.sa-id {
  margin-left: auto;
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 11px;
  color: #888;
  white-space: nowrap;
  flex-shrink: 0;
}

/* ── 回答区（同 tavily AI 摘要） ── */
.sa-answer {
  padding: 12px 14px;
  background: #f5f5f5;
  border: 1px solid #ddd;
  border-radius: 6px;
}
.sa-answer-label {
  font-size: 10px;
  font-weight: 700;
  color: #666;
  letter-spacing: .8px;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.sa-answer-body {
  font-size: 13px;
  color: #222;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

/* ── 降级 ── */
.sa-raw {
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
