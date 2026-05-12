<template>
  <div class="memory-panel">
    <div class="memory-header">
      <h2>长期记忆叙事</h2>
      <button class="btn-refresh" @click="refresh" :disabled="loading">
        {{ loading ? '刷新中……' : '刷新' }}
      </button>
    </div>
    <div class="memory-body">
      <div v-if="loading && !narrative" class="memory-loading">
        加载中……
      </div>
      <div v-else-if="narrative" class="narrative-content" v-html="rendered"></div>
      <div v-else class="memory-empty">
        暂无记忆叙事。开始一段对话后，AI 会自动生成关于你的记忆。
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { marked } from 'marked'
import { api } from '@/api'

const narrative = ref('')
const loading = ref(false)

const rendered = computed(() => {
  return marked.parse(narrative.value || '') as string
})

async function refresh() {
  loading.value = true
  try {
    const res = await api.getNarrative()
    narrative.value = res.narrative
  } catch {
    narrative.value = ''
  } finally {
    loading.value = false
  }
}

onMounted(() => refresh())
</script>

<style scoped>
.memory-panel {
  max-width: 768px;
  margin: 0 auto;
}
.memory-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}
.memory-header h2 {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}
.btn-refresh {
  padding: 6px 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  transition: background 0.15s;
}
.btn-refresh:hover:not(:disabled) {
  background: var(--bg-secondary);
}
.memory-body {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px;
}
.narrative-content {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-primary);
}
.narrative-content :deep(h1),
.narrative-content :deep(h2),
.narrative-content :deep(h3) {
  margin: 16px 0 8px;
  font-weight: 600;
}
.narrative-content :deep(p) {
  margin: 8px 0;
}
.narrative-content :deep(ul),
.narrative-content :deep(ol) {
  padding-left: 20px;
  margin: 8px 0;
}
.narrative-content :deep(li) {
  margin: 4px 0;
}
.narrative-content :deep(code) {
  background: var(--bg-primary);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
}
.narrative-content :deep(pre) {
  background: var(--bg-primary);
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
}
.memory-empty,
.memory-loading {
  color: var(--text-secondary);
  font-size: 14px;
  text-align: center;
  padding: 40px 0;
}
</style>
