<template>
  <div class="word-card info-card">
    <div class="card-header">
      <WordIcon />
      <div class="header-text">
        <div class="card-title">文档信息</div>
        <div class="card-filename" v-if="data.filename || data.file_name">📄 {{ data.filename || data.file_name }}</div>
      </div>
    </div>
    <div class="info-grid">
      <div class="info-item" v-if="data.author">
        <span class="info-label">作者</span>
        <span class="info-value">{{ data.author }}</span>
      </div>
      <div class="info-item" v-if="data.title">
        <span class="info-label">标题</span>
        <span class="info-value">{{ data.title }}</span>
      </div>
      <div class="info-item" v-if="data.paragraph_count !== undefined">
        <span class="info-label">段落</span>
        <span class="info-value">{{ data.paragraph_count }}</span>
      </div>
      <div class="info-item" v-if="data.table_count !== undefined">
        <span class="info-label">表格</span>
        <span class="info-value">{{ data.table_count }}</span>
      </div>
      <div class="info-item" v-if="data.character_count !== undefined">
        <span class="info-label">字符</span>
        <span class="info-value">{{ formatNumber(data.character_count) }}</span>
      </div>
      <div class="info-item" v-if="data.heading_count !== undefined">
        <span class="info-label">标题</span>
        <span class="info-value">{{ data.heading_count }}</span>
      </div>
      <div class="info-item" v-if="data.section_count !== undefined">
        <span class="info-label">节</span>
        <span class="info-value">{{ data.section_count }}</span>
      </div>
      <div class="info-item" v-if="data.page_count !== undefined">
        <span class="info-label">页数</span>
        <span class="info-value">{{ data.page_count }}</span>
      </div>
      <div class="info-item" v-if="data.file_size">
        <span class="info-label">大小</span>
        <span class="info-value">{{ formatSize(data.file_size) }}</span>
      </div>
      <div class="info-item" v-if="data.created">
        <span class="info-label">创建</span>
        <span class="info-value">{{ data.created }}</span>
      </div>
      <div class="info-item" v-if="data.modified">
        <span class="info-label">修改</span>
        <span class="info-value">{{ data.modified }}</span>
      </div>
      <div class="info-item" v-if="data.revision">
        <span class="info-label">修订</span>
        <span class="info-value">{{ data.revision }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import WordIcon from '../_shared/WordIcon.vue'

defineProps<{ data: Record<string, any> }>()

function formatNumber(n: number | string): string {
  const num = typeof n === 'string' ? parseInt(n, 10) : n
  if (isNaN(num)) return String(n)
  return num.toLocaleString()
}

function formatSize(size: number | string): string {
  const bytes = typeof size === 'string' ? parseInt(size, 10) : size
  if (isNaN(bytes)) return String(size)
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
</script>

<style scoped>
.word-card { padding: 12px 4px; }
.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
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
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 1px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--border);
  background: var(--border);
}
.info-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 10px 8px;
  background: var(--bg-primary);
}
.info-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.info-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
</style>
