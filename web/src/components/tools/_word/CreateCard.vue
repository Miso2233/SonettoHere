<template>
  <div class="word-card success-card">
    <div class="card-body">
      <div class="status-badge success">✓</div>
      <div class="card-text">
        <div class="card-title">{{ titleText }}</div>
        <div class="card-filename" v-if="data.filename">📄 {{ data.filename }}</div>
        <div class="card-meta" v-if="data.count">共合并 {{ data.count }} 个文档</div>
      </div>
    </div>
    <div class="card-msg" v-if="data.message">{{ truncate(data.message, 120) }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ data: Record<string, any> }>()

const titleText = computed(() => {
  switch (props.data.action) {
    case 'create_document': return '文档创建成功'
    case 'copy_document': return '文档复制成功'
    case 'merge_documents': return '文档合并成功'
    default: return '操作成功'
  }
})

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n) + '...' : s
}
</script>

<style scoped>
.word-card {
  padding: 12px 4px;
}
.success-card .card-body {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.status-badge {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
}
.status-badge.success {
  background: #dcfce7;
  color: #16a34a;
}
.card-text { flex: 1; }
.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #16a34a;
  margin-bottom: 4px;
}
.card-filename {
  font-size: 13px;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  padding: 4px 8px;
  border-radius: 4px;
  display: inline-block;
}
.card-meta {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}
.card-msg {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  background: var(--bg-primary);
  padding: 8px 10px;
  border-radius: 6px;
}
</style>
