<template>
  <div class="memory-panel">
    <MomentCard />
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
      <div v-else-if="narrative" class="markdown-body" v-html="rendered"></div>
      <div v-else class="memory-empty">
        暂无记忆叙事。开始一段对话后，AI 会自动生成关于你的记忆。
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { renderMarkdown } from '@/utils/markdown'
import { api } from '@/api'
import MomentCard from '@/components/MomentCard.vue'

const narrative = ref('')
const loading = ref(false)

const rendered = computed(() => {
  return renderMarkdown(narrative.value)
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
.memory-body .markdown-body {
  line-height: 1.8;
}
.memory-empty,
.memory-loading {
  color: var(--text-secondary);
  font-size: 14px;
  text-align: center;
  padding: 40px 0;
}
</style>
