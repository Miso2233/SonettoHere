<template>
  <BubbleChrome :tool-call="toolCall">
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>执行调试...</span>
    </div>

    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '调试失败' }}
    </div>

    <template v-else-if="toolCall.status === 'done'">
      <div v-if="hasData" class="db-result">
        <!-- ═══ get_doc 模式 ═══ -->
        <div v-if="td.operation === 'get_doc'" class="db-doc">
          <div class="db-doc-header">调试器说明</div>
          <div class="db-doc-body">{{ td.content }}</div>
        </div>

        <!-- ═══ 代码执行结果 ═══ -->
        <template v-else>
          <!-- 状态徽章 -->
          <div class="db-status-bar">
            <span class="db-badge" :class="isSuccess ? 'db-badge-ok' : 'db-badge-err'">
              {{ isSuccess ? '✓ 执行成功' : '✕ 执行异常' }}
            </span>
          </div>

          <!-- 输出 -->
          <div v-if="isSuccess && td.output" class="db-section">
            <div class="bubble-section-title">输出</div>
            <div class="db-output">{{ td.output }}</div>
          </div>

          <!-- 错误详情 -->
          <div v-if="!isSuccess" class="db-section">
            <div class="bubble-section-title">错误</div>
            <div class="db-error-card">
              <div class="db-error-type">{{ td.error_type }}</div>
              <div class="db-error-msg">{{ td.error_message }}</div>
            </div>
            <div v-if="td.traceback" class="db-tb-wrap">
              <div class="db-tb-header" @click="showTraceback = !showTraceback">
                <span>完整回溯</span>
                <span class="db-toggle">{{ showTraceback ? '▾' : '▸' }}</span>
              </div>
              <pre v-if="showTraceback" class="db-tb">{{ td.traceback }}</pre>
            </div>
          </div>

          <!-- 变量 -->
          <div v-if="hasVariables" class="db-section">
            <div class="bubble-section-title">变量监视</div>
            <div class="db-var-list">
              <div v-for="(val, key) in td.variables" :key="String(key)" class="db-var-item">
                <span class="db-var-key">{{ String(key) }}</span>
                <span class="db-var-val">{{ val }}</span>
              </div>
            </div>
          </div>
        </template>
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

const isSuccess = computed(() => td.value.status === 'success')

const hasVariables = computed(() => {
  const v = td.value.variables
  return v && typeof v === 'object' && Object.keys(v).length > 0
})

const showTraceback = ref(false)

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

.db-result { display: flex; flex-direction: column; gap: 12px; padding: 4px 0; }
.db-section { display: flex; flex-direction: column; gap: 8px; }

/* ── 状态条 ── */
.db-status-bar { padding: 4px 0; }
.db-badge { display: inline-block; font-size: 13px; font-weight: 700; padding: 6px 14px; border-radius: 6px; }
.db-badge-ok { background: #e8f5e9; color: #2e7d32; }
.db-badge-err { background: #fbe9e7; color: #c62828; }

/* ── 输出 ── */
.db-output { font-size: 13px; color: var(--text-primary); padding: 10px 12px; background: var(--bg-primary); border: 1px solid var(--border); border-radius: 6px; }

/* ── 错误 ── */
.db-error-card { display: flex; flex-direction: column; gap: 6px; padding: 10px 12px; background: #fbe9e7; border: 1px solid #ffcdd2; border-radius: 6px; }
.db-error-type { font-size: 13px; font-weight: 700; color: #c62828; font-family: 'SF Mono', 'Consolas', monospace; }
.db-error-msg { font-size: 12px; color: #b71c1c; }
.db-tb-wrap { border: 1px solid var(--border); border-radius: 6px; overflow: hidden; }
.db-tb-header { display: flex; align-items: center; justify-content: space-between; padding: 8px 10px; background: var(--bg-secondary); cursor: pointer; font-size: 12px; font-weight: 600; color: var(--text-secondary); user-select: none; }
.db-tb-header:hover { opacity: 0.8; }
.db-toggle { font-size: 12px; }
.db-tb { font-size: 11px; color: var(--text-primary); line-height: 1.5; padding: 10px; margin: 0; max-height: 250px; overflow-y: auto; font-family: 'SF Mono', 'Consolas', monospace; white-space: pre; background: var(--bg-primary); }

/* ── 变量 ── */
.db-var-list { display: flex; flex-direction: column; gap: 3px; }
.db-var-item { display: flex; align-items: center; gap: 10px; padding: 6px 10px; background: var(--bg-primary); border: 1px solid var(--border); border-radius: 4px; font-size: 12px; }
.db-var-key { font-weight: 700; color: var(--accent); font-family: 'SF Mono', 'Consolas', monospace; flex-shrink: 0; min-width: 80px; }
.db-var-val { color: var(--text-primary); font-family: 'SF Mono', 'Consolas', monospace; word-break: break-all; }

/* ── 文档模式 ── */
.db-doc { display: flex; flex-direction: column; gap: 8px; padding: 4px 0; }
.db-doc-header { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.db-doc-body { font-size: 12px; color: var(--text-primary); white-space: pre-wrap; line-height: 1.6; padding: 10px 12px; background: var(--bg-primary); border: 1px solid var(--border); border-radius: 6px; max-height: 300px; overflow-y: auto; }

.raw-output { font-family: 'SF Mono', 'Consolas', monospace; font-size: 12px; color: var(--text-primary); white-space: pre-wrap; word-break: break-word; margin: 0; padding: 8px 12px; background: var(--bg-primary); border-radius: 6px; }
</style>
