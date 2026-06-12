<template>
  <BubbleChrome :tool-call="toolCall">
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>正在搜索...</span>
    </div>

    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '搜索失败' }}
    </div>

    <template v-else-if="toolCall.status === 'done'">
      <div v-if="hasData" class="ts">
        <div class="ts-query-bar">
          <span class="ts-query-text">{{ queryText }}</span>
          <span class="ts-stats">{{ resultCount }} 条结果 · {{ responseTime }}ms</span>
        </div>

        <div v-if="answerText" class="ts-answer">
          <div class="ts-answer-label">AI 摘要</div>
          <div class="ts-answer-body">{{ answerText }}</div>
        </div>

        <div v-if="items.length" class="ts-list">
          <div v-for="(item, i) in items" :key="i" class="ts-item">
            <div class="ts-item-head">
              <span class="ts-rank">{{ i + 1 }}</span>
              <a class="ts-link" :href="item.url" target="_blank" rel="noopener noreferrer" @click.prevent="openUrl(item.url)">{{ item.title || item.url }}</a>
            </div>
            <div class="ts-url">{{ item.url }}</div>
            <p class="ts-snippet">{{ item.content }}</p>
            <div class="ts-meta">
              <span v-if="item.score != null" class="ts-tag">相关度 {{ (item.score * 100).toFixed(0) }}%</span>
              <span v-if="item.published_date" class="ts-date">{{ item.published_date }}</span>
            </div>

            <div v-if="item.raw_content" class="ts-raw">
              <button class="ts-raw-btn" @click="toggleRaw(i)">{{ expandedRaw.has(i) ? '− 收起全文' : '+ 展开全文' }}</button>
              <div v-if="expandedRaw.has(i)" class="ts-raw-body">{{ item.raw_content }}</div>
            </div>
          </div>
        </div>

        <div v-else class="ts-empty">无结果</div>
      </div>

      <div v-else class="raw-output">{{ fallback }}</div>
    </template>
  </BubbleChrome>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'

const props = defineProps<{ toolCall: ToolCall }>()
const emit = defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

const expandedRaw = ref<Set<number>>(new Set())

function toggleRaw(i: number) {
  const s = expandedRaw.value
  s.has(i) ? s.delete(i) : s.add(i)
  expandedRaw.value = new Set(s)
}

const td = computed<Record<string, any>>(() => {
  if (props.toolCall.toolData) return props.toolCall.toolData as Record<string, any>
  if (props.toolCall.output) {
    try { const p = JSON.parse(props.toolCall.output); if (p?.data) return p.data as Record<string, any> } catch { /* */ }
  }
  return {}
})

const hasData = computed(() => Object.keys(td.value).length > 0)

const queryText = computed(() => td.value.query || '')
const answerText = computed(() => td.value.answer || '')
const responseTime = computed(() => td.value.response_time ?? 0)
const items = computed<Array<Record<string, any>>>(() => Array.isArray(td.value.results) ? td.value.results : [])
const resultCount = computed(() => items.value.length)

function openUrl(url: string) {
  emit('action', { action: 'open_url', data: { url } })
  window.open(url, '_blank', 'noopener,noreferrer')
}

const fallback = computed(() => props.toolCall.output
  ? (props.toolCall.output.length > 500 ? props.toolCall.output.slice(0, 500) + '…' : props.toolCall.output)
  : null)
</script>

<style scoped>
/* ── 布局常量 ── */
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

.ts {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px 0;
}

/* ── 查询栏 ── */
.ts-query-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #f5f5f5;
  border-radius: 6px;
  flex-wrap: wrap;
}
.ts-query-text {
  font-size: 14px;
  font-weight: 600;
  color: #000;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ts-stats {
  font-size: 11px;
  color: #888;
  white-space: nowrap;
  flex-shrink: 0;
}

/* ── AI 摘要 ── */
.ts-answer {
  padding: 12px 14px;
  background: #f5f5f5;
  border: 1px solid #ddd;
  border-radius: 6px;
}
.ts-answer-label {
  font-size: 10px;
  font-weight: 700;
  color: #666;
  letter-spacing: .8px;
  text-transform: uppercase;
  margin-bottom: 6px;
}
.ts-answer-body {
  font-size: 13px;
  color: #222;
  line-height: 1.7;
}

/* ── 结果列表 ── */
.ts-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ts-item {
  padding: 10px 12px;
  border: 1px solid #e0e0e0;
  border-radius: 6px;
  transition: border-color .15s;
}
.ts-item:hover { border-color: #000; }

.ts-item-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.ts-rank {
  font-size: 11px;
  font-weight: 700;
  color: #000;
  flex-shrink: 0;
  min-width: 18px;
  text-align: center;
}

.ts-link {
  font-size: 14px;
  font-weight: 600;
  color: #000;
  cursor: pointer;
  text-decoration: none;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ts-link:hover { text-decoration: underline; }

.ts-url {
  font-size: 11px;
  color: #888;
  margin: 2px 0 0 26px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ts-snippet {
  font-size: 13px;
  color: #444;
  line-height: 1.5;
  margin: 4px 0 0 26px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.ts-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 6px 0 0 26px;
  flex-wrap: wrap;
}

.ts-tag {
  font-size: 10px;
  padding: 1px 6px;
  border: 1px solid #ccc;
  border-radius: 2px;
  color: #555;
  font-weight: 600;
}

.ts-date {
  font-size: 11px;
  color: #999;
}

/* ── 全文折叠 ── */
.ts-raw {
  margin: 8px 0 0 26px;
}

.ts-raw-btn {
  font-size: 11px;
  color: #555;
  background: none;
  border: 1px solid #ccc;
  border-radius: 3px;
  padding: 2px 8px;
  cursor: pointer;
  transition: background .15s;
}
.ts-raw-btn:hover { background: #eee; }

.ts-raw-body {
  margin-top: 8px;
  padding: 10px 12px;
  background: #fafafa;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.7;
  color: #333;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 400px;
  overflow-y: auto;
}

/* ── 无结果 ── */
.ts-empty {
  text-align: center;
  padding: 28px 16px;
  color: #999;
  font-size: 13px;
}

/* ── 降级 ── */
.raw-output {
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
