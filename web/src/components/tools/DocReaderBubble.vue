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
      <div v-if="hasData" class="dr-result">
        <!-- ═══ 文件信息卡片 ═══ -->
        <div class="dr-file-card">
          <span class="dr-file-icon">📝</span>
          <div class="dr-file-info">
            <div class="dr-file-name">{{ fileName }}</div>
            <div class="dr-file-path">{{ filePath }}</div>
          </div>
          <div class="dr-file-stats">
            <span class="dr-stat-badge">{{ paragraphCount }} 段</span>
            <span v-if="tableCount" class="dr-stat-badge">{{ tableCount }} 表</span>
          </div>
        </div>

        <!-- ═══ 元数据 ═══ -->
        <div v-if="metaItems.length" class="dr-section">
          <div class="bubble-section-title">文档信息</div>
          <div class="dr-meta-grid">
            <div v-for="(item, i) in metaItems" :key="i" class="dr-meta-cell">
              <span class="dr-meta-key">{{ item.label }}</span>
              <span class="dr-meta-val">{{ item.value }}</span>
            </div>
          </div>
        </div>

        <!-- ═══ 段落列表 ═══ -->
        <div v-if="paragraphsList.length" class="dr-section">
          <div class="bubble-section-title">
            段落
            <span class="dr-section-sub">{{ td.paragraph_range ? `第 ${td.paragraph_range[0] + 1}–${td.paragraph_range[1] + 1} 段` : `共 ${td.total_paragraphs || paragraphsList.length} 段` }}</span>
          </div>
          <div class="dr-paragraphs">
            <div
              v-for="(para, i) in paragraphsList"
              :key="i"
              class="dr-para"
            >
              <div class="dr-para-header">
                <span class="dr-para-idx">#{{ (para.number || para.index) ?? i + 1 }}</span>
                <span v-if="para.style && para.style !== 'Normal'" class="dr-para-style">{{ para.style }}</span>
              </div>
              <div class="dr-para-text">{{ para.text || '(空)' }}</div>
            </div>
          </div>
        </div>

        <!-- ═══ 文本内容（extract_text 模式） ═══ -->
        <div v-if="td.text" class="dr-section">
          <div class="bubble-section-title">
            文本内容
            <span v-if="td.paragraph_range" class="dr-section-sub">第 {{ td.paragraph_range[0] + 1 }}–{{ td.paragraph_range[1] + 1 }} 段</span>
          </div>
          <div class="dr-text-box">{{ td.text }}</div>
        </div>

        <!-- ═══ 表格 ═══ -->
        <div v-if="tablesList.length" class="dr-section">
          <div class="bubble-section-title">表格（共 {{ tablesList.length }} 个）</div>
          <div
            v-for="(table, i) in tablesList"
            :key="i"
            class="dr-table-card"
          >
            <div class="dr-table-header">表格 {{ i + 1 }} · {{ table.rows }} 行 × {{ table.columns }} 列</div>
            <div class="dr-table-scroll">
              <table class="dr-table">
                <tr v-for="(row, ri) in table.data" :key="ri" class="dr-tr">
                  <td v-for="(cell, ci) in row" :key="ci" class="dr-td">{{ cell }}</td>
                </tr>
              </table>
            </div>
          </div>
        </div>

        <!-- ═══ 搜索结果 ═══ -->
        <div v-if="searchResultsList.length" class="dr-section">
          <div class="bubble-section-title">
            搜索结果：{{ searchQuery }}
            <span class="dr-section-sub">共 {{ totalMatches }} 处匹配</span>
          </div>
          <div class="dr-search-results">
            <div
              v-for="(r, i) in searchResultsList"
              :key="i"
              class="dr-search-item"
            >
              <span class="dr-search-idx">#{{ (r.paragraph_number || r.paragraph_index) ?? i + 1 }}</span>
              <span class="dr-search-text">{{ r.content }}</span>
            </div>
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
const paragraphCount = computed(() => td.value.paragraph_count || td.value.total_paragraphs || 0)
const tableCount = computed(() => td.value.table_count || 0)

// ── 运行中文字 ──
const runningLabel = computed(() => {
  switch (currentOp.value) {
    case 'get_metadata': return '读取元数据...'
    case 'extract_text': return '提取文本...'
    case 'search_text': return '搜索文本...'
    case 'get_paragraphs': return '获取段落...'
    case 'get_tables': return '读取表格...'
    default: return '读取文档...'
  }
})

// ── 元数据 ──
const metaDefs: Record<string, string> = {
  title: '标题', author: '作者', subject: '主题',
  created: '创建时间', modified: '修改时间',
  last_modified_by: '最后修改', keywords: '关键词', category: '类别',
}
const metaItems = computed<Array<{ label: string; value: string }>>(() => {
  const m = td.value.metadata
  if (!m || typeof m !== 'object') return []
  return Object.entries(metaDefs)
    .filter(([key]) => m[key])
    .map(([key, label]) => ({ label, value: m[key] }))
})

// ── 段落 ──
const paragraphsList = computed<Array<Record<string, any>>>(() => {
  const p = td.value.paragraphs
  return Array.isArray(p) ? p : []
})

// ── 表格 ──
const tablesList = computed<Array<Record<string, any>>>(() => {
  const t = td.value.tables
  return Array.isArray(t) ? t : []
})

// ── 搜索结果 ──
const searchResultsList = computed<Array<Record<string, any>>>(() => {
  const r = td.value.results
  return Array.isArray(r) ? r : []
})
const searchQuery = computed(() => td.value.query || '')
const totalMatches = computed(() => td.value.total_matches ?? 0)

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
.dr-result { display: flex; flex-direction: column; gap: 12px; padding: 4px 0; }
.dr-section { display: flex; flex-direction: column; gap: 8px; }

/* ── 文件卡片 ── */
.dr-file-card {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 14px; background: var(--bg-secondary); border-radius: 8px;
}
.dr-file-icon { font-size: 24px; flex-shrink: 0; }
.dr-file-info { flex: 1; min-width: 0; }
.dr-file-name { font-size: 14px; font-weight: 600; color: var(--text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dr-file-path { font-size: 11px; color: var(--text-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dr-file-stats { display: flex; gap: 4px; flex-shrink: 0; }
.dr-stat-badge {
  font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 4px;
  background: var(--bg-primary); color: var(--text-secondary);
}

/* ── 元数据网格 ── */
.dr-meta-grid { display: flex; flex-wrap: wrap; gap: 6px; }
.dr-meta-cell {
  flex: 1; min-width: 140px; display: flex; flex-direction: column; gap: 2px;
  padding: 8px 10px; background: var(--bg-primary); border: 1px solid var(--border); border-radius: 6px;
}
.dr-meta-key { font-size: 10px; font-weight: 600; color: var(--text-secondary); text-transform: uppercase; letter-spacing: 0.3px; }
.dr-meta-val { font-size: 13px; color: var(--text-primary); word-break: break-all; }

/* ── 段落列表 ── */
.dr-section-sub { font-size: 11px; font-weight: 400; color: var(--text-secondary); margin-left: 6px; }
.dr-paragraphs { display: flex; flex-direction: column; gap: 6px; }
.dr-para {
  padding: 8px 10px; background: var(--bg-primary); border: 1px solid var(--border); border-radius: 6px;
}
.dr-para-header { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.dr-para-idx { font-size: 11px; font-weight: 700; color: var(--accent); }
.dr-para-style { font-size: 10px; padding: 1px 6px; border-radius: 3px; background: var(--bg-secondary); color: var(--text-secondary); }
.dr-para-text { font-size: 13px; color: var(--text-primary); line-height: 1.5; }

/* ── 文本内容 ── */
.dr-text-box {
  font-family: 'SF Mono', 'Consolas', monospace; font-size: 12px; line-height: 1.6;
  color: var(--text-primary); white-space: pre-wrap; word-break: break-word;
  padding: 10px 12px; background: var(--bg-primary); border: 1px solid var(--border);
  border-radius: 6px; max-height: 300px; overflow-y: auto;
}

/* ── 表格 ── */
.dr-table-card {
  border: 1px solid var(--border); border-radius: 6px; overflow: hidden;
}
.dr-table-header {
  font-size: 11px; font-weight: 600; color: var(--accent);
  padding: 6px 10px; background: var(--bg-secondary);
}
.dr-table-scroll { overflow-x: auto; }
.dr-table { border-collapse: collapse; width: 100%; font-size: 12px; }
.dr-tr { border-bottom: 1px solid var(--border); }
.dr-tr:last-child { border-bottom: none; }
.dr-td {
  padding: 6px 8px; color: var(--text-primary); white-space: nowrap;
  border-right: 1px solid var(--border); min-width: 80px;
}
.dr-td:last-child { border-right: none; }

/* ── 搜索结果 ── */
.dr-search-results { display: flex; flex-direction: column; gap: 4px; }
.dr-search-item {
  display: flex; gap: 8px; padding: 6px 10px;
  background: var(--bg-primary); border: 1px solid var(--border); border-radius: 6px;
}
.dr-search-idx { font-size: 11px; font-weight: 700; color: var(--accent); flex-shrink: 0; min-width: 28px; }
.dr-search-text { font-size: 13px; color: var(--text-primary); line-height: 1.5; }

/* ── 降级 ── */
.raw-output {
  font-family: 'SF Mono', 'Consolas', monospace; font-size: 12px;
  color: var(--text-primary); white-space: pre-wrap; word-break: break-word;
  margin: 0; padding: 8px 12px; background: var(--bg-primary); border-radius: 6px;
}
</style>
