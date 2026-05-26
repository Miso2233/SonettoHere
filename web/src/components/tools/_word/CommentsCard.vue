<template>
  <div class="word-card comments-card">
    <div class="card-header">
      <span class="cmt-icon">💬</span>
      <div>
        <div class="card-title">{{ titleText }}</div>
        <div class="card-filename" v-if="data.filename">📄 {{ data.filename }}</div>
      </div>
    </div>

    <div class="cmt-summary" v-if="data.count !== undefined">
      <span class="cmt-badge">{{ data.count }}</span>
      <span class="cmt-label">条评论</span>
    </div>

    <div class="cmt-list" v-if="data.comments?.length">
      <div class="cmt-item" v-for="(c, i) in data.comments.slice(0, 10)" :key="i">
        <div class="cmt-author" v-if="c.author || c.author_name">
          <span class="cmt-avatar">👤</span>
          {{ c.author || c.author_name }}
        </div>
        <div class="cmt-text">{{ truncate(c.text || c.content || '', 150) }}</div>
      </div>
      <div class="cmt-more" v-if="data.comments.length > 10">
        … 还有 {{ data.comments.length - 10 }} 条评论
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ data: Record<string, any> }>()

const titleText = computed(() => {
  const a = props.data.action
  if (a?.includes('by_author')) return '评论（按作者）'
  if (a?.includes('for_paragraph')) return '段落评论'
  return '文档评论'
})

function truncate(s: string, n: number): string {
  return s && s.length > n ? s.slice(0, n) + '...' : s || ''
}
</script>

<style scoped>
.word-card { padding: 12px 4px; }
.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.cmt-icon { font-size: 20px; }
.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #0891b2;
}
.card-filename {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}
.cmt-summary {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
}
.cmt-badge {
  background: #ecfeff;
  color: #0891b2;
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 700;
}
.cmt-label { font-size: 13px; color: var(--text-secondary); }
.cmt-list {
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
}
.cmt-item {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  font-size: 12px;
}
.cmt-item:last-child { border-bottom: none; }
.cmt-author {
  display: flex;
  align-items: center;
  gap: 4px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 4px;
}
.cmt-avatar { font-size: 12px; }
.cmt-text {
  color: var(--text-secondary);
  line-height: 1.5;
  word-break: break-word;
}
.cmt-more {
  padding: 6px;
  font-size: 11px;
  color: var(--text-secondary);
  text-align: center;
  background: var(--bg-secondary);
}
</style>
