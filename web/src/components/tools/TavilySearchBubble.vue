<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 运行中 -->
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>正在搜索...</span>
    </div>

    <!-- 错误 -->
    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '搜索失败' }}
    </div>

    <!-- 完成 -->
    <template v-else-if="toolCall.status === 'done'">
      <div v-if="hasData" class="tv-search">
        <!-- 搜索概览 -->
        <div class="tv-query-bar">
          <span class="tv-query-text">{{ queryText }}</span>
          <span class="tv-stats">{{ resultCount }} 条结果 · {{ responseTime }}ms</span>
        </div>

        <!-- AI 回答横幅 -->
        <div v-if="answerText" class="tv-answer">
          <div class="tv-answer-label">AI 摘要</div>
          <div class="tv-answer-content">{{ answerText }}</div>
        </div>

        <!-- 结果列表 -->
        <div v-if="items.length" class="tv-list">
          <div v-for="(item, i) in items" :key="i" class="tv-item">
            <div class="tv-item-header">
              <span class="tv-rank">{{ i + 1 }}</span>
              <a
                class="tv-title"
                :href="item.url"
                target="_blank"
                rel="noopener noreferrer"
                @click.prevent="openUrl(item.url)"
              >{{ item.title || item.url }}</a>
            </div>
            <div class="tv-url">{{ item.url }}</div>
            <div class="tv-snippet">{{ item.content }}</div>
            <div class="tv-meta">
              <span v-if="item.score != null" class="tv-score">相关度 {{ (item.score * 100).toFixed(0) }}%</span>
              <span v-if="item.published_date" class="tv-date">{{ item.published_date }}</span>
            </div>

            <!-- 全文内容（折叠） -->
            <div v-if="item.raw_content" class="tv-raw-toggle">
              <button class="tv-toggle-btn" @click="toggleRaw(i)">
                {{ expandedRaw.has(i) ? '收起全文' : '展开全文' }}
              </button>
              <div v-if="expandedRaw.has(i)" class="tv-raw-content">{{ item.raw_content }}</div>
            </div>
          </div>
        </div>

        <div v-else class="tv-empty">未找到相关结果</div>
      </div>

      <!-- 降级 -->
      <div v-else>
        <div class="raw-output">{{ displayOutput }}</div>
      </div>
    </template>
  </BubbleChrome>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'

const props = defineProps<{ toolCall: ToolCall }>()
const emit = defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

// 展开的全文索引集合
const expandedRaw = ref<Set<number>>(new Set())

function toggleRaw(i: number) {
  const s = expandedRaw.value
  if (s.has(i)) s.delete(i)
  else s.add(i)
  // 触发重新渲染
  expandedRaw.value = new Set(s)
}

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
const queryText = computed(() => td.value.query || '')
const answerText = computed(() => td.value.answer || '')
const responseTime = computed(() => td.value.response_time ?? 0)

const items = computed<Array<Record<string, any>>>(() => {
  const results = td.value.results
  return Array.isArray(results) ? results : []
})

const resultCount = computed(() => items.value.length)

// ── 打开链接 ──
function openUrl(url: string) {
  emit('action', { action: 'open_url', data: { url } })
  window.open(url, '_blank', 'noopener,noreferrer')
}

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

.bubble-error {
  font-size: 13px;
  color: #b91c1c;
  padding: 4px 0;
}

/* ── 主容器 ── */
.tv-search {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 4px 0;
}

/* ── 搜索概览栏 ── */
.tv-query-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: var(--bg-secondary);
  border-radius: 8px;
  flex-wrap: wrap;
}

.tv-query-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tv-stats {
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
  flex-shrink: 0;
}

/* ── AI 回答 ── */
.tv-answer {
  padding: 10px 14px;
  background: #f0f7ff;
  border: 1px solid #cce5ff;
  border-radius: 8px;
}

.tv-answer-label {
  font-size: 11px;
  font-weight: 700;
  color: #1a6bb0;
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.tv-answer-content {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.6;
}

/* ── 结果列表 ── */
.tv-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tv-item {
  padding: 10px 12px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 8px;
  transition: border-color 0.15s;
}

.tv-item:hover {
  border-color: var(--accent-light);
}

.tv-item-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.tv-rank {
  font-size: 11px;
  font-weight: 700;
  color: var(--accent);
  flex-shrink: 0;
  min-width: 18px;
  text-align: center;
}

.tv-title {
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

.tv-title:hover {
  text-decoration: underline;
  color: #134d82;
}

.tv-url {
  font-size: 11px;
  color: #0a7a3a;
  margin: 2px 0 0 26px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tv-snippet {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
  margin: 4px 0 0 26px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.tv-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 6px 0 0 26px;
  flex-wrap: wrap;
}

.tv-score {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  background: #e8f5e9;
  color: #27ae60;
  font-weight: 600;
}

.tv-date {
  font-size: 11px;
  color: var(--text-secondary);
}

/* ── 全文折叠 ── */
.tv-raw-toggle {
  margin: 8px 0 0 26px;
}

.tv-toggle-btn {
  font-size: 11px;
  color: #1a6bb0;
  background: none;
  border: 1px solid #cce5ff;
  border-radius: 4px;
  padding: 2px 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.tv-toggle-btn:hover {
  background: #f0f7ff;
}

.tv-raw-content {
  margin-top: 8px;
  padding: 10px 12px;
  background: #fafafa;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 400px;
  overflow-y: auto;
}

/* ── 空结果 ── */
.tv-empty {
  text-align: center;
  padding: 32px 16px;
  color: var(--text-secondary);
  font-size: 13px;
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
