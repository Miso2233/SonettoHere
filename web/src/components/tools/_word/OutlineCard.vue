<template>
  <div class="word-card outline-card">
    <div class="card-header">
      <WordIcon />
      <div class="header-text">
        <div class="card-title">{{ titleText }}</div>
        <div class="card-filename" v-if="data.filename || data.file_name">📄 {{ data.filename || data.file_name }}</div>
      </div>
    </div>

    <!-- 统计摘要 -->
    <div class="stats-row" v-if="hasStats">
      <div class="stat-pill" v-if="data.heading_count !== undefined">
        <span class="stat-num">{{ data.heading_count }}</span> 个标题
      </div>
      <div class="stat-pill" v-if="data.paragraph_count !== undefined">
        <span class="stat-num">{{ data.paragraph_count }}</span> 个段落
      </div>
      <div class="stat-pill" v-if="data.count !== undefined">
        <span class="stat-num">{{ data.count }}</span> 个文档
      </div>
    </div>

    <!-- 文档列表 -->
    <div class="file-list" v-if="data.files?.length">
      <div class="file-row" v-for="(f, i) in data.files.slice(0, 15)" :key="i">
        <span class="file-icon">📄</span>
        <span class="file-name">{{ typeof f === 'string' ? f : f.name || f.filename || '' }}</span>
        <span class="file-size" v-if="f.size">{{ formatSize(f.size) }}</span>
      </div>
      <div class="file-more" v-if="data.files.length > 15">… 还有 {{ data.files.length - 15 }} 个文档</div>
    </div>

    <!-- 标题大纲 -->
    <div class="heading-list" v-if="data.headings?.length">
      <div class="heading-row" v-for="(h, i) in data.headings.slice(0, 20)" :key="i"
           :style="{ paddingLeft: ((h.level || 1) - 1) * 16 + 'px' }">
        <span class="heading-bullet">•</span>
        <span class="heading-text">{{ h.text || h.title || '' }}</span>
      </div>
      <div class="file-more" v-if="data.headings.length > 20">… 还有 {{ data.headings.length - 20 }} 个标题</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import WordIcon from '../_shared/WordIcon.vue'

const props = defineProps<{ data: Record<string, any> }>()

const titleText = computed(() => {
  switch (props.data.action) {
    case 'get_document_outline': return '文档大纲'
    case 'list_documents': return '文档列表'
    case 'get_document_xml': return '文档 XML'
    case 'get_document_text': return '文档文本'
    default: return '文档概览'
  }
})

const hasStats = computed(() => {
  return props.data.heading_count !== undefined ||
         props.data.paragraph_count !== undefined ||
         props.data.count !== undefined
})

function formatSize(size: number | string): string {
  const bytes = typeof size === 'string' ? parseInt(size, 10) : size
  if (isNaN(bytes)) return String(size)
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
</script>

<style scoped>
.word-card { padding: 12px 4px; }
.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}
.header-text { flex: 1; }
.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}
.card-filename {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

/* Stats */
.stats-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.stat-pill {
  background: var(--bg-secondary);
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  color: var(--text-secondary);
}
.stat-num {
  font-weight: 700;
  color: var(--accent);
}

/* File list */
.file-list {
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
}
.file-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  font-size: 12px;
  border-bottom: 1px solid var(--border);
}
.file-row:last-child { border-bottom: none; }
.file-icon { flex-shrink: 0; }
.file-name { flex: 1; color: var(--text-primary); word-break: break-all; }
.file-size { color: var(--text-secondary); flex-shrink: 0; }
.file-more {
  padding: 8px 10px;
  font-size: 11px;
  color: var(--text-secondary);
  text-align: center;
  background: var(--bg-secondary);
}

/* Headings */
.heading-list {
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
}
.heading-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  font-size: 12px;
  border-bottom: 1px solid var(--border);
}
.heading-row:last-child { border-bottom: none; }
.heading-bullet { color: var(--accent); flex-shrink: 0; }
.heading-text { color: var(--text-primary); }
</style>
