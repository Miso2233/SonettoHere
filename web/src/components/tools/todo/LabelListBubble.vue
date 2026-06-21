<template>
  <div class="card-lineframe">
    <!-- 头部 -->
    <div class="lf-header">
      <div class="lf-header-left">
        <div class="lf-tool-label">Labels · {{ total }}</div>
        <div class="lf-timestamp">{{ total === 0 ? '未定义标签' : '' }}</div>
      </div>
    </div>

    <!-- 标签网格 -->
    <div v-if="labels.length" class="label-grid">
      <span v-for="l in labels" :key="l.label_id" class="lg-tag">
        {{ l.name }}
      </span>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">暂无标签</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ toolData?: Record<string, any> }>()

const total = computed(() => props.toolData?.total ?? 0)
const labels = computed<Array<Record<string, any>>>(() => {
  const list = props.toolData?.labels
  return Array.isArray(list) ? list : []
})

</script>

<style scoped>
.card-lineframe {
  border: 1px solid var(--border);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  background: var(--bg-primary);
  border-radius: 2px;
}
.lf-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.lf-header-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.lf-tool-label {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--text-secondary);
}
.lf-timestamp {
  font-size: 10px;
  color: var(--text-tertiary, #bbb);
  letter-spacing: 0.3px;
}
/* ── 标签列表 ── */
.label-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.lg-tag {
  font-size: 11px;
  color: var(--text-secondary);
  border: 1px solid var(--border);
  padding: 4px 12px;
  border-radius: 2px;
  letter-spacing: 0.3px;
}
/* ── 空状态 ── */
.empty-state {
  text-align: center;
  padding: 24px 0;
  font-size: 12px;
  color: var(--text-tertiary, #ccc);
  letter-spacing: 0.3px;
}
</style>
