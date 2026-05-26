<template>
  <div class="word-card footnote-card">
    <div class="card-header">
      <span class="fn-icon">{{ isEndnote ? '📝' : '①' }}</span>
      <div>
        <div class="card-title">{{ titleText }}</div>
        <div class="card-filename" v-if="data.filename">📄 {{ data.filename }}</div>
      </div>
    </div>

    <!-- 脚注统计 -->
    <div class="fn-stats" v-if="data.footnote_count !== undefined">
      <span class="fn-badge">{{ data.footnote_count }}</span>
      <span class="fn-label">{{ isEndnote ? '个尾注' : '个脚注' }}</span>
    </div>

    <!-- 验证结果 -->
    <div class="fn-valid" v-if="data.action === 'validate_footnotes'">
      {{ data.message || '脚注验证完成' }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ data: Record<string, any> }>()

const isEndnote = computed(() => props.data.action?.includes('endnote'))

const titleText = computed(() => {
  const a = props.data.action
  if (!a) return '脚注操作'
  if (a.includes('add_footnote')) return '添加脚注'
  if (a.includes('delete_footnote')) return '删除脚注'
  if (a.includes('customize')) return '自定义脚注样式'
  if (a.includes('validate')) return '验证脚注'
  if (a.includes('add_endnote')) return '添加尾注'
  return a.replace(/_/g, ' ')
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
.fn-icon {
  font-size: 20px;
  line-height: 1;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #fff7ed;
  border-radius: 50%;
}
.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #c2410c;
}
.card-filename {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}
.fn-stats {
  display: flex;
  align-items: center;
  gap: 6px;
}
.fn-badge {
  background: #fff7ed;
  color: #c2410c;
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 700;
}
.fn-label {
  font-size: 13px;
  color: var(--text-secondary);
}
.fn-valid {
  font-size: 13px;
  color: var(--text-primary);
  padding: 6px 0;
  line-height: 1.5;
}
</style>
