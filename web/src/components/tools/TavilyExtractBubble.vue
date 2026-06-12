<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 运行中 -->
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>正在提取内容...</span>
    </div>

    <!-- 错误 -->
    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '提取失败' }}
    </div>

    <!-- 完成 -->
    <template v-else-if="toolCall.status === 'done'">
      <div v-if="hasData" class="tv-extract">
        <!-- 结果概览 -->
        <div class="tv-summary">
          <span class="tv-summary-text">提取 {{ successCount }} 个页面 · {{ responseTime }}ms</span>
          <span v-if="failCount" class="tv-fail-badge">{{ failCount }} 个失败</span>
        </div>

        <!-- 多 URL Tab -->
        <div v-if="pages.length > 0" class="tv-tabs">
          <button
            v-for="(page, i) in pages"
            :key="i"
            class="tv-tab"
            :class="{ active: activeTab === i }"
            @click="activeTab = i"
          >
            {{ page.title || page.url.slice(0, 30) + '…' }}
          </button>
        </div>

        <!-- 当前 Tab 内容 -->
        <div v-if="currentPage" class="tv-page">
          <div class="tv-page-header">
            <a
              class="tv-page-title"
              :href="currentPage.url"
              target="_blank"
              rel="noopener noreferrer"
              @click.prevent="openUrl(currentPage.url)"
            >{{ currentPage.title || currentPage.url }}</a>
            <div class="tv-page-url">{{ currentPage.url }}</div>
          </div>

          <!-- 图片列表 -->
          <div v-if="currentPage.images && currentPage.images.length" class="tv-images">
            <div class="bubble-section-title">图片 ({{ currentPage.images.length }})</div>
            <div class="tv-image-list">
              <img
                v-for="(img, j) in currentPage.images"
                :key="j"
                :src="img"
                class="tv-image-thumb"
                alt=""
                @click="openUrl(img)"
              />
            </div>
          </div>

          <!-- Markdown 正文 -->
          <div v-if="currentPage.raw_content" class="tv-content-section">
            <div class="tv-content-header">
              <span class="bubble-section-title">正文内容</span>
              <button class="tv-toggle-btn" @click="contentExpanded = !contentExpanded">
                {{ contentExpanded ? '收起' : '展开全部' }}
              </button>
            </div>
            <div
              class="tv-content-body"
              :class="{ collapsed: !contentExpanded }"
            >{{ currentPage.raw_content }}</div>
          </div>

          <div v-else class="tv-no-content">该页面无正文内容</div>
        </div>

        <!-- 失败列表 -->
        <div v-if="failedItems.length" class="tv-failed">
          <div class="bubble-section-title">失败的页面</div>
          <div v-for="(f, i) in failedItems" :key="i" class="tv-failed-item">
            <span class="tv-failed-url">{{ f.url }}</span>
            <span v-if="f.error" class="tv-failed-error">{{ f.error }}</span>
          </div>
        </div>
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

const activeTab = ref(0)
const contentExpanded = ref(false)

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

const responseTime = computed(() => td.value.response_time ?? 0)

// ── 成功页面 ──
const pages = computed<Array<Record<string, any>>>(() => {
  const results = td.value.results
  return Array.isArray(results) ? results : []
})

const successCount = computed(() => pages.value.length)

// ── 失败页面 ──
const failedItems = computed<Array<Record<string, any>>>(() => {
  const failed = td.value.failed_results
  return Array.isArray(failed) ? failed : []
})

const failCount = computed(() => failedItems.value.length)

// ── 当前 Tab ──
const currentPage = computed(() => {
  return pages.value[activeTab.value] || null
})

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
.tv-extract {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 4px 0;
}

/* ── 摘要 ── */
.tv-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: var(--bg-secondary);
  border-radius: 8px;
  font-size: 12px;
  flex-wrap: wrap;
}

.tv-summary-text {
  color: var(--text-primary);
  font-weight: 500;
}

.tv-fail-badge {
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 3px;
  background: #fde8e8;
  color: #c0392b;
}

/* ── Tab 栏 ── */
.tv-tabs {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.tv-tab {
  font-size: 11px;
  padding: 4px 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-primary);
  color: var(--text-primary);
  cursor: pointer;
  transition: all 0.15s;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tv-tab:hover {
  border-color: var(--accent-light);
}

.tv-tab.active {
  background: #1a6bb0;
  color: #fff;
  border-color: #1a6bb0;
}

/* ── 页面内容 ── */
.tv-page {
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
}

.tv-page-header {
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
}

.tv-page-title {
  font-size: 15px;
  font-weight: 600;
  color: #1a6bb0;
  cursor: pointer;
  text-decoration: none;
  display: block;
  line-height: 1.4;
}

.tv-page-title:hover {
  text-decoration: underline;
}

.tv-page-url {
  font-size: 11px;
  color: #0a7a3a;
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── 图片 ── */
.tv-images {
  margin-bottom: 10px;
}

.tv-image-list {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 6px;
}

.tv-image-thumb {
  width: 80px;
  height: 60px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid var(--border);
  cursor: pointer;
  transition: opacity 0.15s;
}

.tv-image-thumb:hover {
  opacity: 0.8;
}

/* ── 正文 ── */
.tv-content-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tv-content-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
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

.tv-content-body {
  font-size: 12px;
  line-height: 1.7;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: none;
  overflow-y: visible;
}

.tv-content-body.collapsed {
  max-height: 300px;
  overflow-y: hidden;
  position: relative;
}

.tv-content-body.collapsed::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 60px;
  background: linear-gradient(transparent, var(--bg-primary));
  pointer-events: none;
}

.tv-no-content {
  font-size: 13px;
  color: var(--text-secondary);
  text-align: center;
  padding: 24px;
}

/* ── 失败列表 ── */
.tv-failed {
  border: 1px solid #fde8e8;
  border-radius: 8px;
  padding: 10px 12px;
  background: #fff5f5;
}

.tv-failed-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 6px 0;
  font-size: 12px;
  border-top: 1px solid #fde8e8;
}

.tv-failed-item:first-child {
  border-top: none;
}

.tv-failed-url {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 11px;
  color: var(--text-primary);
  word-break: break-all;
}

.tv-failed-error {
  font-size: 11px;
  color: #c0392b;
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
