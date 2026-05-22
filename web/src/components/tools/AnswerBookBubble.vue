<template>
  <BubbleChrome :tool-call="toolCall">
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>翻阅答案之书...</span>
    </div>

    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '查询失败' }}
    </div>

    <template v-else-if="toolCall.status === 'done'">
      <div v-if="answer" class="book-result">
        <div class="book-cover">
          <div class="book-icon">&#128214;</div>
          <div class="book-title">答案之书</div>
          <div class="book-subtitle">The Book of Answers</div>
        </div>

        <div class="book-question">
          <div class="q-label">你的问题</div>
          <div class="q-text">{{ question }}</div>
        </div>

        <div class="book-divider">
          <span class="divider-icon">&#10024;</span>
        </div>

        <div class="book-answer">
          <div class="a-label">答案</div>
          <div class="a-text">&ldquo;{{ answer }}&rdquo;</div>
        </div>
      </div>

      <div v-else class="raw-output">{{ displayOutput }}</div>
    </template>
  </BubbleChrome>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'

const props = defineProps<{ toolCall: ToolCall }>()
const emit = defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

// ── 数据源：优先 toolData，降级到 parse output ──
const data = computed(() => {
  if (props.toolCall.toolData) return props.toolCall.toolData
  if (props.toolCall.output) {
    try {
      const p = JSON.parse(props.toolCall.output)
      if (p?.data) return p.data
    } catch {
      /* intentional */ // eslint-disable-line
    }
  }
  return null
})

const question = computed(() => {
  const q = data.value?.question as string | undefined
  if (q) return q
  // 从 input 中提取
  try {
    const input = JSON.parse(props.toolCall.input)
    if (input?.question) return input.question
  } catch { /* ignore */ }
  return '未记录'
})

const answer = computed(() => (data.value?.answer as string) || '')

const displayOutput = computed(() => {
  if (props.toolCall.output) {
    return props.toolCall.output.length > 500
      ? props.toolCall.output.slice(0, 500) + '...'
      : props.toolCall.output
  }
  return null
})
</script>

<style scoped>
/* ── 运行中 ── */
.bubble-running {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  flex-shrink: 0;
}

@keyframes spin { to { transform: rotate(360deg); } }

.bubble-error {
  font-size: 13px;
  color: #b91c1c;
  padding: 4px 0;
}

/* ── 书本样式 ── */
.book-result {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 4px 0;
}

/* ── 书封 ── */
.book-cover {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 20px 32px;
  background: linear-gradient(135deg, #2c1810, #4a2c20);
  border-radius: 10px;
  width: 100%;
  max-width: 260px;
}

.book-icon {
  font-size: 32px;
  line-height: 1;
}

.book-title {
  font-size: 18px;
  font-weight: 700;
  color: #f0e6d3;
  letter-spacing: 2px;
}

.book-subtitle {
  font-size: 11px;
  color: #c4a882;
  font-style: italic;
  letter-spacing: 1px;
}

/* ── 问题 ── */
.book-question {
  width: 100%;
  text-align: center;
}

.q-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 4px;
}

.q-text {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
  line-height: 1.5;
}

/* ── 分隔线 ── */
.book-divider {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.divider-icon {
  font-size: 18px;
  opacity: 0.6;
}

/* ── 答案 ── */
.book-answer {
  width: 100%;
  text-align: center;
  padding: 12px 16px;
  background: var(--bg-primary);
  border-radius: 8px;
}

.a-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-bottom: 6px;
}

.a-text {
  font-size: 22px;
  font-weight: 600;
  color: var(--accent);
  line-height: 1.4;
}

/* ── 降级 ── */
.raw-output {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  padding: 8px 12px;
  background: var(--bg-primary);
  border-radius: 6px;
}
</style>
