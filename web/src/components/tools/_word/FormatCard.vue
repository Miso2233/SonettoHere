<template>
  <div class="word-card format-card">
    <div class="card-header">
      <span class="fmt-icon">🎨</span>
      <div class="header-text">
        <div class="card-title">{{ titleText }}</div>
        <div class="card-filename" v-if="data.filename">📄 {{ data.filename }}</div>
      </div>
    </div>
    <div class="card-msg">{{ data.message || '格式已应用' }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ data: Record<string, any> }>()

const titleText = computed(() => {
  switch (props.data.action) {
    case 'format_text': return '格式化文本'
    case 'format_table': return '格式化表格'
    case 'create_style': return '创建样式'
    default: return '格式操作'
  }
})
</script>

<style scoped>
.word-card { padding: 12px 4px; }
.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.fmt-icon { font-size: 22px; }
.header-text { flex: 1; }
.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #7c3aed;
}
.card-filename {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}
.card-msg {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
}
</style>
