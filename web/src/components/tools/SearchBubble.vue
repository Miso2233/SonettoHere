<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 运行中（spinner 在 BubbleChrome header 中，此处仅文字） -->
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>正在搜索...</span>
    </div>

    <!-- 错误 -->
    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '搜索失败' }}
    </div>

    <!-- 完成 -->
    <template v-else-if="toolCall.status === 'done'">
      <div v-if="hasData" class="sr-result">
        <!-- 搜索概览 -->
        <div class="sr-query-bar">
          <span class="sr-query-icon">🔍</span>
          <span class="sr-query-text">{{ searchQuery }}</span>
          <span class="sr-stats">{{ totalResults }} 条结果 · {{ processTime }}ms</span>
        </div>

        <!-- 搜索结果列表 -->
        <div v-if="resultList.length" class="sr-list">
          <div
            v-for="(item, i) in resultList"
            :key="i"
            class="sr-item"
          >
            <div class="sr-item-header">
              <span class="sr-rank">{{ item.position ?? i + 1 }}</span>
              <a
                class="sr-title"
                :href="item.url"
                target="_blank"
                rel="noopener noreferrer"
                @click.prevent="openUrl(item.url)"
              >{{ item.title }}</a>
            </div>
            <div class="sr-url">{{ item.url }}</div>
            <div class="sr-snippet">{{ item.snippet }}</div>
            <div class="sr-meta">
              <span class="sr-domain">{{ item.domain }}</span>
              <span v-if="item.publish_time" class="sr-date">{{ formatTime(item.publish_time) }}</span>
              <span v-if="item.score" class="sr-score">相关度 {{ (item.score * 100).toFixed(0) }}%</span>
            </div>
          </div>
        </div>

        <div v-else class="sr-empty">未找到相关结果</div>

        <!-- 搜索引擎信息 -->
        <div v-if="sourceList.length" class="sr-sources">
          <div class="bubble-section-title">搜索引擎</div>
          <div class="sr-sources-list">
            <div
              v-for="(src, i) in sourceList"
              :key="i"
              class="sr-source"
            >
              <span class="sr-source-name">{{ src.name }}</span>
              <span
                class="sr-source-status"
                :class="src.status"
              >{{ statusLabel(src.status) }}</span>
              <span class="sr-source-detail">{{ src.result_count }} 条 · {{ src.elapsed_ms }}ms</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 降级：显示调试信息 -->
      <div v-else>
        <div class="raw-output">{{ displayOutput }}</div>
        <details class="sr-debug" v-if="hasToolDataDebug">
          <summary>调试信息</summary>
          <div class="sr-debug-content">
            <div class="debug-row"><span class="debug-label">toolCall.name:</span><code>{{ props.toolCall.name }}</code></div>
            <div class="debug-row"><span class="debug-label">toolCall.status:</span><code>{{ props.toolCall.status }}</code></div>
            <div class="debug-row"><span class="debug-label">has toolData:</span><code>{{ !!props.toolCall.toolData }}</code></div>
            <div class="debug-row" v-if="props.toolCall.toolData"><span class="debug-label">toolData type:</span><code>{{ typeof props.toolCall.toolData }}</code></div>
            <div class="debug-row"><span class="debug-label">has output:</span><code>{{ !!props.toolCall.output }}</code></div>
            <div class="debug-row" v-if="props.toolCall.output"><span class="debug-label">output length:</span><code>{{ props.toolCall.output.length }}</code></div>
            <div class="debug-row" v-if="props.toolCall.output"><span class="debug-label">output preview:</span><code>{{ props.toolCall.output.slice(0, 150) }}</code></div>
          </div>
        </details>
      </div>
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

// ── 核心字段 ──
const searchQuery = computed(() => td.value.query || '')
const totalResults = computed(() => td.value.total_results ?? 0)
const processTime = computed(() => td.value.process_time_ms ?? td.value.process_time ?? 0)

// ── 结果列表 ──
const resultList = computed<Array<Record<string, any>>>(() => {
  const results = td.value.results
  if (!Array.isArray(results)) return []
  return [...results].sort((a, b) => (a.position ?? 99) - (b.position ?? 99))
})

// ── 搜索源 ──
const sourceList = computed<Array<Record<string, any>>>(() => {
  const sources = td.value.sources
  return Array.isArray(sources) ? sources : []
})

function statusLabel(status: string): string {
  switch (status) {
    case 'success': return '成功'
    case 'fail': return '失败'
    case 'error': return '错误'
    default: return status
  }
}

// ── 时间格式化 ──
function formatTime(iso: string): string {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return iso
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffDays = Math.floor(diffMs / 86400000)
    if (diffDays === 0) return '今天'
    if (diffDays === 1) return '昨天'
    if (diffDays < 7) return `${diffDays} 天前`
    // 格式化为 YYYY-MM-DD
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${y}-${m}-${day}`
  } catch {
    return iso
  }
}

// ── 打开链接 ──
function openUrl(url: string) {
  emit('action', { action: 'open_url', data: { url } })
  window.open(url, '_blank', 'noopener,noreferrer')
}

// ── 降级调试 ──
const hasToolDataDebug = computed(() =>
  !!props.toolCall.toolData || !!props.toolCall.output
)

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
  color: #c05050;
  padding: 4px 0;
}

/* ── 主容器 ── */
.sr-result {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 4px 0;
}

/* ── 搜索概览栏 ── */
.sr-query-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: var(--bg-secondary);
  border-radius: 8px;
  flex-wrap: wrap;
}

.sr-query-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.sr-query-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sr-stats {
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
  flex-shrink: 0;
}

/* ── 搜索结果列表 ── */
.sr-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sr-item {
  padding: 10px 12px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 8px;
  transition: border-color 0.15s;
}

.sr-item:hover {
  border-color: var(--accent-light);
}

.sr-item-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.sr-rank {
  font-size: 11px;
  font-weight: 700;
  color: var(--accent);
  flex-shrink: 0;
  min-width: 18px;
  text-align: center;
}

.sr-title {
  font-size: 14px;
  font-weight: 600;
  color: #1a6bb0;
  cursor: pointer;
  text-decoration: none;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sr-title:hover {
  text-decoration: underline;
  color: #134d82;
}

.sr-url {
  font-size: 11px;
  color: #0a7a3a;
  margin: 2px 0 0 26px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sr-snippet {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
  margin: 4px 0 0 26px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.sr-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 6px 0 0 26px;
  flex-wrap: wrap;
}

.sr-domain {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
}

.sr-date {
  font-size: 11px;
  color: var(--text-secondary);
}

.sr-score {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  background: #e8f5e9;
  color: #27ae60;
  font-weight: 600;
}

/* ── 空结果 ── */
.sr-empty {
  text-align: center;
  padding: 32px 16px;
  color: var(--text-secondary);
  font-size: 13px;
}

/* ── 搜索引擎信息 ── */
.sr-sources {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  background: var(--bg-primary);
}

.sr-sources-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sr-source {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  padding: 4px 0;
}

.sr-source-name {
  font-weight: 600;
  color: var(--text-primary);
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 11px;
  min-width: 120px;
}

.sr-source-status {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 3px;
  text-transform: uppercase;
}

.sr-source-status.success {
  background: #e8f5e9;
  color: #27ae60;
}

.sr-source-status.fail,
.sr-source-status.error {
  background: #fde8e8;
  color: #c0392b;
}

.sr-source-detail {
  color: var(--text-secondary);
  margin-left: auto;
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

/* ── 调试信息 ── */
.sr-debug {
  margin-top: 8px;
  border: 1px dashed #d4a0a0;
  border-radius: 6px;
  padding: 6px 10px;
  background: #fff8f0;
  font-size: 12px;
}

.sr-debug summary {
  cursor: pointer;
  font-weight: 600;
  color: #8b3a3a;
  font-size: 11px;
  user-select: none;
}

.sr-debug-content {
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.debug-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.debug-label {
  font-weight: 600;
  color: #8b3a3a;
  min-width: 120px;
  flex-shrink: 0;
  font-size: 11px;
}

.debug-row code {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 11px;
  color: #333;
  word-break: break-all;
}
</style>
