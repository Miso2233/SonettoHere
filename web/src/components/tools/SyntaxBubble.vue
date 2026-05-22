<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 运行中 -->
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>正在检查语法...</span>
    </div>

    <!-- 错误 -->
    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '检查失败' }}
    </div>

    <!-- 完成 -->
    <template v-else-if="toolCall.status === 'done'">
      <div v-if="hasData" class="syntax-result">
        <!-- 摘要 -->
        <div class="syntax-summary" :class="summaryClass">
          <span class="summary-icon">{{ summaryIcon }}</span>
          <span class="summary-text">{{ summaryText }}</span>
          <span class="summary-lang">{{ language }}</span>
        </div>

        <!-- 错误列表 -->
        <div v-if="errors.length" class="syntax-list">
          <div class="syntax-list-title">错误（{{ errors.length }}）</div>
          <div v-for="(err, i) in errors" :key="'e'+i" class="syntax-item error-item">
            <span v-if="err.line" class="si-pos">第 {{ err.line }} 行</span>
            <span v-if="err.column" class="si-pos">列 {{ err.column }}</span>
            <span class="si-msg">{{ err.message }}</span>
          </div>
        </div>

        <!-- 警告列表 -->
        <div v-if="warnings.length" class="syntax-list">
          <div class="syntax-list-title">警告（{{ warnings.length }}）</div>
          <div v-for="(w, i) in warnings" :key="'w'+i" class="syntax-item warn-item">
            <span v-if="w.line" class="si-pos">第 {{ w.line }} 行</span>
            <span class="si-msg">{{ w.message }}</span>
          </div>
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

const language = computed(() => td.value.language || '')
const errors = computed<Array<Record<string, any>>>(() => {
  const raw = td.value.errors
  return Array.isArray(raw) ? raw : []
})
const warnings = computed<Array<Record<string, any>>>(() => {
  const raw = td.value.warnings
  return Array.isArray(raw) ? raw : []
})

const hasIssues = computed(() => errors.value.length > 0 || warnings.value.length > 0)

const summaryClass = computed(() => hasIssues.value ? 'has-errors' : 'all-clear')
const summaryIcon = computed(() => hasIssues.value ? '✗' : '✓')
const summaryText = computed(() => {
  if (!hasIssues.value) return '语法检查通过'
  const parts: string[] = []
  if (errors.value.length) parts.push(`${errors.value.length} 个错误`)
  if (warnings.value.length) parts.push(`${warnings.value.length} 个警告`)
  return `发现 ${parts.join('，')}`
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
.syntax-result {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 4px 0;
}

/* ── 摘要 ── */
.syntax-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
}

.syntax-summary.all-clear {
  background: #e8f5e9;
  color: #2e7d32;
}

.syntax-summary.has-errors {
  background: #fde8e8;
  color: #c0392b;
}

.summary-icon {
  font-size: 18px;
}

.summary-lang {
  margin-left: auto;
  font-size: 11px;
  font-weight: 500;
  opacity: 0.7;
}

/* ── 列表 ── */
.syntax-list {
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  background: var(--bg-primary);
}

.syntax-list-title {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-secondary);
  padding: 8px 12px 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.syntax-item {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 6px 12px 6px 12px;
  font-size: 13px;
  line-height: 1.4;
}

.syntax-item:last-child {
  padding-bottom: 10px;
}

.si-pos {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.si-msg {
  color: var(--text-primary);
  word-break: break-word;
}

.error-item .si-msg {
  color: #c0392b;
}

.warn-item .si-msg {
  color: #e65100;
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
