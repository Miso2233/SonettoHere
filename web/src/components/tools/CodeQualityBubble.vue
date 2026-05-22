<template>
  <BubbleChrome :tool-call="toolCall">
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>分析代码质量...</span>
    </div>

    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '分析失败' }}
    </div>

    <template v-else-if="toolCall.status === 'done'">
      <div v-if="hasData" class="cq-result">
        <!-- ═══ 文件信息 ═══ -->
        <div v-if="td.file_path" class="cq-file-card">
          <span class="cq-file-icon">🔍</span>
          <div class="cq-file-info">
            <div class="cq-file-name">{{ fileName }}</div>
            <div class="cq-file-path">{{ td.file_path }}</div>
          </div>
          <div class="cq-badge">{{ analysisTypeLabel }}</div>
        </div>

        <!-- ═══ Complexity ═══ -->
        <div v-if="complexity" class="cq-section">
          <div class="bubble-section-title">圈复杂度</div>
          <div class="cq-metrics">
            <div class="cq-metric"><span class="cq-metric-val">{{ complexity.total_lines }}</span><span class="cq-metric-lbl">总行数</span></div>
            <div class="cq-metric"><span class="cq-metric-val">{{ complexity.function_count }}</span><span class="cq-metric-lbl">函数数</span></div>
            <div class="cq-metric"><span class="cq-metric-val">{{ complexity.avg_function_length.toFixed(1) }}</span><span class="cq-metric-lbl">平均函数长度</span></div>
          </div>
          <div v-if="complexity.functions?.length" class="cq-func-list">
            <div v-for="(fn, i) in complexity.functions" :key="i" class="cq-func-item">
              <span class="cq-func-name">{{ fn.name }}</span>
              <span class="cq-func-lines">L{{ fn.line }}–{{ fn.endline }} ({{ fn.endline - fn.line + 1 }} 行)</span>
            </div>
          </div>
        </div>

        <!-- ═══ Maintainability ═══ -->
        <div v-if="maintainability" class="cq-section">
          <div class="bubble-section-title">可维护性</div>
          <div class="cq-metrics">
            <div class="cq-metric">
              <span class="cq-metric-val" :class="scoreColorClass">{{ maintainability.maintainability_score }}</span>
              <span class="cq-metric-lbl">可维护性评分</span>
            </div>
            <div class="cq-metric"><span class="cq-metric-val">{{ (maintainability.comment_ratio * 100).toFixed(0) }}%</span><span class="cq-metric-lbl">注释率</span></div>
            <div class="cq-metric"><span class="cq-metric-val">{{ maintainability.snake_case_count }}</span><span class="cq-metric-lbl">snake_case</span></div>
            <div class="cq-metric"><span class="cq-metric-val">{{ maintainability.camel_case_count }}</span><span class="cq-metric-lbl">camelCase</span></div>
          </div>
        </div>

        <!-- ═══ Duplication ═══ -->
        <div v-if="duplication" class="cq-section">
          <div class="bubble-section-title">重复代码</div>
          <div class="cq-metrics">
            <div class="cq-metric"><span class="cq-metric-val">{{ duplication.duplicate_lines }}</span><span class="cq-metric-lbl">重复行数</span></div>
            <div class="cq-metric"><span class="cq-metric-val">{{ (duplication.duplicate_ratio * 100).toFixed(1) }}%</span><span class="cq-metric-lbl">重复率</span></div>
          </div>
          <div v-if="duplication.duplicates?.length" class="cq-dup-list">
            <div v-for="(d, i) in duplication.duplicates" :key="i" class="cq-dup-item">
              <code class="cq-dup-code">{{ d.line }}</code>
              <span class="cq-dup-count">重复 {{ d.count }} 次</span>
            </div>
          </div>
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
defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

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

const fileName = computed(() => {
  const path = td.value.file_path || ''
  return path.split('/').pop()?.split('\\').pop() || path || '代码分析'
})

const analysisTypeLabel = computed(() => {
  const map: Record<string, string> = {
    complexity: '复杂度', maintainability: '可维护性',
    duplication: '重复度', all: '全面分析',
  }
  return map[td.value.analysis_type] || td.value.analysis_type || '全面分析'
})

const complexity = computed(() => td.value.complexity || null)
const maintainability = computed(() => td.value.maintainability || null)
const duplication = computed(() => td.value.duplication || null)

const scoreColorClass = computed(() => {
  const s = maintainability.value?.maintainability_score
  if (s == null) return ''
  if (s >= 80) return 'score-green'
  if (s >= 50) return 'score-yellow'
  return 'score-red'
})

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
.bubble-running { display: flex; align-items: center; gap: 8px; padding: 8px 0; font-size: 13px; color: var(--text-secondary); }
.spinner { width: 14px; height: 14px; border: 2px solid var(--border); border-top-color: var(--accent); border-radius: 50%; animation: spin 0.6s linear infinite; flex-shrink: 0; }
@keyframes spin { to { transform: rotate(360deg); } }
.bubble-error { font-size: 13px; color: #b91c1c; padding: 4px 0; }

.cq-result { display: flex; flex-direction: column; gap: 12px; padding: 4px 0; }
.cq-section { display: flex; flex-direction: column; gap: 8px; }

.cq-file-card { display: flex; align-items: center; gap: 12px; padding: 12px 14px; background: var(--bg-secondary); border-radius: 8px; }
.cq-file-icon { font-size: 24px; flex-shrink: 0; }
.cq-file-info { flex: 1; min-width: 0; }
.cq-file-name { font-size: 14px; font-weight: 600; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cq-file-path { font-size: 11px; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cq-badge { font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 4px; background: var(--accent); color: #fff; flex-shrink: 0; }

.cq-metrics { display: flex; flex-wrap: wrap; gap: 6px; }
.cq-metric { flex: 1; min-width: 100px; display: flex; flex-direction: column; gap: 2px; padding: 10px 12px; background: var(--bg-primary); border: 1px solid var(--border); border-radius: 6px; text-align: center; }
.cq-metric-val { font-size: 22px; font-weight: 700; color: var(--text-primary); }
.cq-metric-lbl { font-size: 11px; color: var(--text-secondary); }

.score-green { color: #43a047; }
.score-yellow { color: #f9a825; }
.score-red { color: #e53935; }

.cq-func-list { display: flex; flex-direction: column; gap: 2px; padding: 4px 0; }
.cq-func-item { display: flex; align-items: center; gap: 8px; padding: 6px 10px; background: var(--bg-primary); border: 1px solid var(--border); border-radius: 4px; font-size: 13px; }
.cq-func-name { font-weight: 600; color: var(--accent); font-family: 'SF Mono', 'Consolas', monospace; }
.cq-func-lines { font-size: 11px; color: var(--text-secondary); margin-left: auto; }

.cq-dup-list { display: flex; flex-direction: column; gap: 4px; }
.cq-dup-item { display: flex; align-items: center; gap: 8px; padding: 6px 10px; background: var(--bg-primary); border: 1px solid var(--border); border-radius: 4px; font-size: 12px; }
.cq-dup-code { font-family: 'SF Mono', 'Consolas', monospace; color: var(--text-primary); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cq-dup-count { font-size: 11px; color: var(--text-secondary); flex-shrink: 0; }

.raw-output { font-family: 'SF Mono', 'Consolas', monospace; font-size: 12px; color: var(--text-primary); white-space: pre-wrap; word-break: break-word; margin: 0; padding: 8px 12px; background: var(--bg-primary); border-radius: 6px; }
</style>
