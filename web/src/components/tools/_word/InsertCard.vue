<template>
  <div class="word-card insert-card">
    <div class="card-header">
      <span class="insert-icon">{{ insertIcon }}</span>
      <div>
        <div class="card-title">{{ titleText }}</div>
        <div class="card-filename" v-if="data.filename">📄 {{ data.filename }}</div>
      </div>
    </div>

    <!-- 标题信息 -->
    <div class="detail-line" v-if="data.text">
      <span class="detail-label">标题</span>
      <span class="detail-val">「{{ data.text }}」</span>
    </div>
    <div class="detail-line" v-if="data.level">
      <span class="detail-label">级别</span>
      <span class="detail-val">Heading {{ data.level }}</span>
    </div>

    <!-- 图片信息 -->
    <div class="detail-line" v-if="data.image_path">
      <span class="detail-label">图片</span>
      <span class="detail-val path">{{ data.image_path }}</span>
    </div>

    <!-- 目录条目数 -->
    <div class="detail-line" v-if="data.count !== undefined">
      <span class="detail-label">目录条目</span>
      <span class="detail-val">{{ data.count }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ data: Record<string, any> }>()

const insertIcon = computed(() => {
  switch (props.data.action) {
    case 'add_heading': return '🔤'
    case 'add_picture': return '🖼️'
    case 'add_page_break': return '📄'
    case 'add_toc': return '📑'
    case 'insert_list': return '📋'
    default: return '✏️'
  }
})

const titleText = computed(() => {
  switch (props.data.action) {
    case 'add_heading': return '添加标题'
    case 'add_paragraph': return '添加段落'
    case 'add_picture': return '插入图片'
    case 'add_page_break': return '插入分页符'
    case 'add_toc': return '添加目录'
    case 'insert_heading': return '插入标题'
    case 'insert_paragraph': return '插入段落'
    case 'insert_list': return '插入列表'
    default: return '插入内容'
  }
})
</script>

<style scoped>
.word-card { padding: 12px 4px; }
.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.insert-icon { font-size: 24px; line-height: 1; }
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
.detail-line {
  display: flex;
  gap: 8px;
  padding: 4px 0;
  font-size: 13px;
  align-items: baseline;
}
.detail-label {
  color: var(--text-secondary);
  flex-shrink: 0;
  min-width: 4em;
}
.detail-val {
  color: var(--text-primary);
  word-break: break-all;
}
.detail-val.path {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 11px;
  background: var(--bg-primary);
  padding: 2px 6px;
  border-radius: 3px;
}
</style>
