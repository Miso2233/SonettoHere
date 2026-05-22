<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 运行中 -->
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>{{ runningLabel }}</span>
    </div>

    <!-- 错误 -->
    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '读取失败' }}
    </div>

    <!-- 完成 -->
    <template v-else-if="toolCall.status === 'done'">
      <div v-if="hasData" class="pr-result">
        <!-- ═══ 文件信息卡片 ═══ -->
        <div class="pr-file-card">
          <span class="pr-file-icon">📄</span>
          <div class="pr-file-info">
            <div class="pr-file-name">{{ fileName }}</div>
            <div class="pr-file-path">{{ filePath }}</div>
          </div>
          <div class="pr-file-stats">
            <span class="pr-stat-badge">{{ pageCount }} 页</span>
            <span v-if="fileSize" class="pr-stat-badge">{{ fileSize }}</span>
          </div>
        </div>

        <!-- ═══ 元数据 ═══ -->
        <div v-if="metadataKeys.length" class="pr-section">
          <div class="bubble-section-title">文档信息</div>
          <div class="pr-meta-grid">
            <div v-for="(val, key) in td.metadata" :key="key" class="pr-meta-cell">
              <span class="pr-meta-key">{{ prettyKey(String(key)) }}</span>
              <span class="pr-meta-val">{{ val }}</span>
            </div>
          </div>
        </div>

        <!-- ═══ 目录 ═══ -->
        <div v-if="tocList.length" class="pr-section">
          <div class="bubble-section-title">目录</div>
          <div class="pr-toc">
            <div
              v-for="(item, i) in tocList"
              :key="i"
              class="pr-toc-item"
              :style="{ paddingLeft: (item.level || 0) * 16 + 12 + 'px' }"
            >
              <span class="pr-toc-title">{{ item.title }}</span>
              <span v-if="item.page_number" class="pr-toc-page">第 {{ item.page_number }} 页</span>
            </div>
          </div>
        </div>

        <!-- ═══ 文本内容 ═══ -->
        <div v-if="td.text" class="pr-section">
          <div class="bubble-section-title">
            文本内容
            <span v-if="td.page_range" class="pr-section-sub">第 {{ td.page_range[0] + 1 }}–{{ td.page_range[1] + 1 }} 页</span>
          </div>
          <div class="pr-text-box">{{ td.text }}</div>
        </div>

        <!-- ═══ 搜索文本结果 ═══ -->
        <div v-if="searchResults.length" class="pr-section">
          <div class="bubble-section-title">
            搜索结果：{{ searchQuery }}
            <span class="pr-section-sub">共 {{ totalMatches }} 处匹配</span>
          </div>
          <div
            v-for="(page, i) in searchResults"
            :key="i"
            class="pr-search-page"
          >
            <div class="pr-search-page-header">第 {{ page.page_number }} 页</div>
            <div
              v-for="(line, j) in page.matched_lines || []"
              :key="j"
              class="pr-search-line"
            >
              <span class="pr-search-line-no">{{ line.line_number }}</span>
              <span class="pr-search-line-text">{{ line.content }}</span>
            </div>
          </div>
        </div>

        <!-- ═══ 页面提取（多页模式） ═══ -->
        <div v-if="pageContentsList.length" class="pr-section">
          <div class="bubble-section-title">提取的页面</div>
          <div
            v-for="(pc, i) in pageContentsList"
            :key="i"
            class="pr-page-card"
          >
            <div class="pr-page-header">第 {{ pc.page_number || i + 1 }} 页</div>
            <div class="pr-text-box">{{ pc.text }}</div>
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

// ── 操作类型 ──
const currentOp = computed(() => td.value.operation || '')

// ── 文件信息 ──
const fileName = computed(() => {
  const path = td.value.file_path || ''
  return path.split('/').pop()?.split('\\').pop() || path || '未知文件'
})
const filePath = computed(() => td.value.file_path || '')
const pageCount = computed(() => td.value.page_count || td.value.total_pages || 0)
const fileSize = computed(() => {
  const bytes = td.value.size_bytes || td.value.file_size
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
})

// ── 运行中文字 ──
const runningLabel = computed(() => {
  switch (currentOp.value) {
    case 'get_metadata': return '读取元数据...'
    case 'extract_text': return '提取文本...'
    case 'extract_pages': return '提取页面...'
    case 'search_text': return '搜索文本...'
    case 'get_toc': return '解析目录...'
    case 'get_page_count': return '获取页数...'
    default: return '读取 PDF...'
  }
})

// ── 元数据 ──
const metadataKeys = computed(() => {
  const m = td.value.metadata
  return m && typeof m === 'object' ? Object.keys(m).filter(k => m[k]) : []
})

function prettyKey(key: string): string {
  const map: Record<string, string> = {
    '/Title': '标题', '/Author': '作者', '/Subject': '主题',
    '/Keywords': '关键词', '/Creator': '创建工具', '/Producer': '生成器',
    '/CreationDate': '创建时间', '/ModDate': '修改时间',
    title: '标题', author: '作者', subject: '主题',
    keywords: '关键词', creator: '创建工具', producer: '生成器',
  }
  return map[key] || key
}

// ── 目录 ──
const tocList = computed<Array<Record<string, any>>>(() => {
  const toc = td.value.toc
  return Array.isArray(toc) ? toc : []
})

// ── 搜索结果 ──
const searchResults = computed<Array<Record<string, any>>>(() => {
  const r = td.value.results
  return Array.isArray(r) ? r : []
})
const searchQuery = computed(() => td.value.query || '')
const totalMatches = computed(() => td.value.total_matches ?? 0)

// ── 页面提取 ──
const pageContentsList = computed<Array<Record<string, any>>>(() => {
  const pc = td.value.page_contents
  if (pc && typeof pc === 'object') {
    return Object.values(pc).filter((v): v is Record<string, any> => !!v && typeof v === 'object')
  }
  return []
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
/* ── 运行中 ── */
.bubble-running {
  display: flex; align-items: center; gap: 8px; padding: 8px 0;
  font-size: 13px; color: var(--text-secondary);
}
.spinner {
  width: 14px; height: 14px;
  border: 2px solid var(--border); border-top-color: var(--accent);
  border-radius: 50%; animation: spin 0.6s linear infinite; flex-shrink: 0;
}
@keyframes spin { to { transform: rotate(360deg); } }
.bubble-error { font-size: 13px; color: #b91c1c; padding: 4px 0; }

/* ── 主容器 ── */
.pr-result { display: flex; flex-direction: column; gap: 12px; padding: 4px 0; }
.pr-section { display: flex; flex-direction: column; gap: 8px; }

/* ── 文件卡片 ── */
.pr-file-card {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 14px; background: var(--bg-secondary); border-radius: 8px;
}
.pr-file-icon { font-size: 24px; flex-shrink: 0; }
.pr-file-info { flex: 1; min-width: 0; }
.pr-file-name { font-size: 14px; font-weight: 600; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pr-file-path { font-size: 11px; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pr-file-stats { display: flex; gap: 4px; flex-shrink: 0; }
.pr-stat-badge {
  font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 4px;
  background: var(--bg-primary); color: var(--text-secondary);
}

/* ── 元数据网格 ── */
.pr-meta-grid { display: flex; flex-wrap: wrap; gap: 6px; }
.pr-meta-cell {
  flex: 1; min-width: 140px; display: flex; flex-direction: column; gap: 2px;
  padding: 8px 10px; background: var(--bg-primary); border: 1px solid var(--border); border-radius: 6px;
}
.pr-meta-key { font-size: 10px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.3px; }
.pr-meta-val { font-size: 13px; color: var(--text-primary); word-break: break-all; }

/* ── 目录 ── */
.pr-toc { display: flex; flex-direction: column; gap: 2px; padding: 6px 0; }
.pr-toc-item {
  display: flex; align-items: center; gap: 8px;
  padding: 4px 8px; border-radius: 4px; font-size: 13px;
}
.pr-toc-item:hover { background: var(--bg-secondary); }
.pr-toc-title { color: var(--text-primary); flex: 1; }
.pr-toc-page { font-size: 11px; color: var(--accent); font-weight: 600; white-space: nowrap; }

/* ── 文本内容 ── */
.pr-section-sub { font-size: 11px; font-weight: 400; color: var(--text-secondary); margin-left: 6px; }
.pr-text-box {
  font-family: 'SF Mono', 'Consolas', monospace; font-size: 12px; line-height: 1.6;
  color: var(--text-primary); white-space: pre-wrap; word-break: break-word;
  padding: 10px 12px; background: var(--bg-primary); border: 1px solid var(--border);
  border-radius: 6px; max-height: 300px; overflow-y: auto;
}

/* ── 搜索结果 ── */
.pr-search-page { margin-bottom: 8px; }
.pr-search-page:last-child { margin-bottom: 0; }
.pr-search-page-header {
  font-size: 12px; font-weight: 600; color: var(--accent);
  padding: 4px 8px; background: var(--bg-secondary); border-radius: 4px; margin-bottom: 4px;
}
.pr-search-line {
  display: flex; gap: 8px; padding: 2px 8px; font-size: 12px; font-family: 'SF Mono', 'Consolas', monospace;
}
.pr-search-line-no { color: var(--text-secondary); min-width: 24px; text-align: right; flex-shrink: 0; }
.pr-search-line-text { color: var(--text-primary); white-space: pre-wrap; word-break: break-word; }

/* ── 页面提取 ── */
.pr-page-card { margin-bottom: 8px; }
.pr-page-card:last-child { margin-bottom: 0; }
.pr-page-header {
  font-size: 12px; font-weight: 600; color: var(--accent);
  padding: 4px 0; margin-bottom: 4px;
}

/* ── 降级 ── */
.raw-output {
  font-family: 'SF Mono', 'Consolas', monospace; font-size: 12px;
  color: var(--text-primary); white-space: pre-wrap; word-break: break-word;
  margin: 0; padding: 8px 12px; background: var(--bg-primary); border-radius: 6px;
}
</style>
