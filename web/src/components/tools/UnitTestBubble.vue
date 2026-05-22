<template>
  <BubbleChrome :tool-call="toolCall">
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>运行单元测试...</span>
    </div>

    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '测试执行失败' }}
    </div>

    <template v-else-if="toolCall.status === 'done'">
      <div v-if="hasData" class="ut-result">
        <!-- ═══ 成功率环 ═══ -->
        <div class="ut-hero">
          <div class="ut-ring" :class="rateColorClass">
            <span class="ut-ring-text">{{ rateDisplay }}%</span>
            <span class="ut-ring-lbl">通过率</span>
          </div>
          <div class="ut-hero-stats">
            <div class="ut-hero-stat">
              <span class="ut-hero-num">{{ td.tests_run }}</span>
              <span class="ut-hero-desc">总计</span>
            </div>
            <div class="ut-hero-stat">
              <span class="ut-hero-num ut-success">{{ td.successful }}</span>
              <span class="ut-hero-desc">通过</span>
            </div>
            <div class="ut-hero-stat">
              <span class="ut-hero-num ut-fail">{{ td.failures }}</span>
              <span class="ut-hero-desc">失败</span>
            </div>
            <div class="ut-hero-stat">
              <span class="ut-hero-num ut-error">{{ td.errors }}</span>
              <span class="ut-hero-desc">错误</span>
            </div>
            <div class="ut-hero-stat">
              <span class="ut-hero-num ut-skip">{{ td.skipped }}</span>
              <span class="ut-hero-desc">跳过</span>
            </div>
          </div>
        </div>

        <!-- ═══ 失败详情 ═══ -->
        <div v-if="failuresDetails.length" class="ut-section">
          <div class="bubble-section-title">失败详情（{{ failuresDetails.length }}）</div>
          <div v-for="(item, i) in failuresDetails" :key="i" class="ut-detail-card">
            <div class="ut-detail-header" @click="toggleItem(failPanels, i)">
              <span class="ut-detail-icon ut-icon-fail">✕</span>
              <span class="ut-detail-test">{{ item.test }}</span>
              <span class="ut-detail-toggle">{{ failPanels[i] ? '▾' : '▸' }}</span>
            </div>
            <div v-if="failPanels[i]" class="ut-detail-body">
              <div class="ut-detail-field">
                <span class="ut-detail-label">消息</span>
                <code class="ut-detail-msg">{{ item.message }}</code>
              </div>
              <div class="ut-detail-field">
                <span class="ut-detail-label">回溯</span>
                <pre class="ut-detail-tb">{{ item.traceback }}</pre>
              </div>
            </div>
          </div>
        </div>

        <!-- ═══ 错误详情 ═══ -->
        <div v-if="errorsDetails.length" class="ut-section">
          <div class="bubble-section-title">错误详情（{{ errorsDetails.length }}）</div>
          <div v-for="(item, i) in errorsDetails" :key="i" class="ut-detail-card">
            <div class="ut-detail-header" @click="toggleItem(errPanels, i)">
              <span class="ut-detail-icon ut-icon-err">⚠</span>
              <span class="ut-detail-test">{{ item.test }}</span>
              <span class="ut-detail-toggle">{{ errPanels[i] ? '▾' : '▸' }}</span>
            </div>
            <div v-if="errPanels[i]" class="ut-detail-body">
              <div class="ut-detail-field">
                <span class="ut-detail-label">消息</span>
                <code class="ut-detail-msg">{{ item.message }}</code>
              </div>
              <div class="ut-detail-field">
                <span class="ut-detail-label">回溯</span>
                <pre class="ut-detail-tb">{{ item.traceback }}</pre>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="raw-output">{{ displayOutput }}</div>
    </template>
  </BubbleChrome>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
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

const rateDisplay = computed(() => {
  const r = td.value.success_rate
  if (r == null) return 0
  return Math.round(r)
})

const rateColorClass = computed(() => {
  const r = td.value.success_rate ?? 0
  if (r >= 80) return 'rate-green'
  if (r >= 50) return 'rate-yellow'
  return 'rate-red'
})

const failuresDetails = computed<Array<Record<string, any>>>(() => {
  const d = td.value.failures_details
  return Array.isArray(d) ? d : []
})

const errorsDetails = computed<Array<Record<string, any>>>(() => {
  const d = td.value.errors_details
  return Array.isArray(d) ? d : []
})

const failPanels = ref<boolean[]>([])
const errPanels = ref<boolean[]>([])

function toggleItem(arr: boolean[], idx: number) {
  arr[idx] = !arr[idx]
}

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

.ut-result { display: flex; flex-direction: column; gap: 12px; padding: 4px 0; }
.ut-section { display: flex; flex-direction: column; gap: 8px; }

/* ── Hero ── */
.ut-hero { display: flex; align-items: center; gap: 20px; padding: 16px 14px; background: var(--bg-secondary); border-radius: 8px; }
.ut-ring { display: flex; flex-direction: column; align-items: center; justify-content: center; width: 80px; height: 80px; border-radius: 50%; border: 4px solid; flex-shrink: 0; }
.ut-ring.rate-green { border-color: #43a047; }
.ut-ring.rate-yellow { border-color: #f9a825; }
.ut-ring.rate-red { border-color: #e53935; }
.ut-ring-text { font-size: 22px; font-weight: 800; color: var(--text-primary); line-height: 1; }
.ut-ring-lbl { font-size: 10px; color: var(--text-secondary); margin-top: 2px; }
.ut-hero-stats { display: flex; gap: 10px; flex: 1; flex-wrap: wrap; }
.ut-hero-stat { display: flex; flex-direction: column; align-items: center; min-width: 44px; }
.ut-hero-num { font-size: 18px; font-weight: 700; color: var(--text-primary); }
.ut-hero-desc { font-size: 10px; color: var(--text-secondary); }
.ut-success { color: #43a047; }
.ut-fail { color: #e53935; }
.ut-error { color: #fb8c00; }
.ut-skip { color: #90a4ae; }

/* ── Detail Cards ── */
.ut-detail-card { border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }
.ut-detail-header { display: flex; align-items: center; gap: 8px; padding: 8px 10px; background: var(--bg-secondary); cursor: pointer; user-select: none; }
.ut-detail-header:hover { opacity: 0.8; }
.ut-detail-icon { font-size: 14px; flex-shrink: 0; }
.ut-icon-fail { color: #e53935; }
.ut-icon-err { color: #fb8c00; }
.ut-detail-test { flex: 1; font-size: 13px; font-weight: 600; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ut-detail-toggle { font-size: 12px; color: var(--text-secondary); flex-shrink: 0; }
.ut-detail-body { display: flex; flex-direction: column; gap: 8px; padding: 10px 12px; background: var(--bg-primary); }
.ut-detail-field { display: flex; flex-direction: column; gap: 4px; }
.ut-detail-label { font-size: 10px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; }
.ut-detail-msg { font-size: 12px; color: #b91c1c; padding: 6px 8px; background: var(--bg-secondary); border-radius: 4px; font-family: 'SF Mono', 'Consolas', monospace; word-break: break-word; }
.ut-detail-tb { font-size: 11px; color: var(--text-primary); line-height: 1.5; padding: 8px; background: var(--bg-secondary); border-radius: 4px; max-height: 200px; overflow-y: auto; font-family: 'SF Mono', 'Consolas', monospace; white-space: pre; }

.raw-output { font-family: 'SF Mono', 'Consolas', monospace; font-size: 12px; color: var(--text-primary); white-space: pre-wrap; word-break: break-word; margin: 0; padding: 8px 12px; background: var(--bg-primary); border-radius: 6px; }
</style>
