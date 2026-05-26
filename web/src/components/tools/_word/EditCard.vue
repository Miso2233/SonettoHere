<template>
  <div class="word-card edit-card">
    <div class="card-header">
      <span class="edit-icon">✂️</span>
      <div>
        <div class="card-title">{{ titleText }}</div>
        <div class="card-filename" v-if="data.filename">📄 {{ data.filename }}</div>
      </div>
    </div>
    <div class="card-msg">{{ data.message || '编辑完成' }}</div>

    <!-- 段落索引 -->
    <div class="detail-line" v-if="data.paragraph_index !== undefined">
      <span class="dl-label">段落索引</span>
      <span class="dl-val">{{ data.paragraph_index }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ data: Record<string, any> }>()

const titleText = computed(() => {
  switch (props.data.action) {
    case 'delete_paragraph': return '删除段落'
    case 'replace_block': return '替换区块'
    case 'replace_anchors': return '替换锚点内容'
    case 'get_paragraph': return '获取段落'
    default: return '编辑操作'
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
.edit-icon { font-size: 20px; }
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
.card-msg {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
  margin-bottom: 4px;
}
.detail-line {
  display: flex;
  gap: 8px;
  font-size: 12px;
  padding: 2px 0;
}
.dl-label { color: var(--text-secondary); }
.dl-val { color: var(--text-primary); font-weight: 500; }
</style>
