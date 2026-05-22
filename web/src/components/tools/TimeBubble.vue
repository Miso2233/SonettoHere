<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 运行中 -->
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>获取时间...</span>
    </div>

    <!-- 错误 -->
    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '查询失败' }}
    </div>

    <!-- 完成 -->
    <template v-else-if="toolCall.status === 'done'">
      <div v-if="hasData" class="time-result">
        <!-- 大时钟 -->
        <div class="time-display">
          <span class="time-digits">{{ time }}</span>
        </div>

        <!-- 日期行 -->
        <div class="date-row">
          <span class="date-value">{{ date }}</span>
          <span class="weekday-value">{{ weekdayCn }}</span>
        </div>

        <!-- 时区 -->
        <div class="timezone-row">
          <span class="tz-label">时区</span>
          <span class="tz-value">{{ timezone }}</span>
        </div>
      </div>

      <!-- 降级 -->
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

// ── 数据源 ──
const td = computed<Record<string, any>>(() => {
  if (props.toolCall.toolData) return props.toolCall.toolData as Record<string, any>
  if (props.toolCall.output) {
    try {
      const p = JSON.parse(props.toolCall.output)
      if (p?.data) return p.data as Record<string, any>
    } catch { /* ignore */ }
  }
  return {}
})

const hasData = computed(() => Object.keys(td.value).length > 0)

// ── 字段 ──
const date = computed(() => td.value.date || '')
const time = computed(() => td.value.time || '')
const timezone = computed(() => td.value.timezone || '')
const weekday = computed(() => td.value.weekday || '')

const weekdayCn = computed(() => {
  const map: Record<string, string> = {
    Monday: '星期一', Tuesday: '星期二', Wednesday: '星期三',
    Thursday: '星期四', Friday: '星期五', Saturday: '星期六', Sunday: '星期日',
  }
  return map[weekday.value] || weekday.value
})

// ── 降级 ──
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

/* ── 主容器 ── */
.time-result {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 20px 12px;
}

/* ── 大时钟 ── */
.time-display {
  padding: 16px 24px;
  border-radius: 16px;
}

.time-digits {
  font-size: 48px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--accent);
  letter-spacing: 2px;
}

/* ── 日期行 ── */
.date-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.date-value {
  font-size: 18px;
  font-weight: 500;
  color: var(--text-primary);
}

.weekday-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--accent);
  padding: 2px 10px;
  border-radius: 4px;
  background: color-mix(in srgb, var(--accent) 12%, transparent);
}

/* ── 时区 ── */
.timezone-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
  padding: 6px 12px;
  border-radius: 6px;
  background: var(--bg-secondary);
}

.tz-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.tz-value {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 500;
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
