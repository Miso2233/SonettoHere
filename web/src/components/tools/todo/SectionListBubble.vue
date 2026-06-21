<template>
  <div class="card-lineframe">
    <!-- 头部 -->
    <div class="lf-header">
      <div class="lf-header-left">
        <div class="lf-tool-label">{{ headerLabel }}</div>
        <div class="lf-timestamp">{{ total }} section{{ total !== 1 ? 's' : '' }}</div>
      </div>
    </div>

    <!-- 分区列表 -->
    <div v-if="sections.length" class="section-tree">
      <div v-for="s in sections" :key="s.section_id" class="st-node">
        <div class="st-row">
          <span class="st-name">{{ s.name }}</span>
          <span v-if="s.project_name" class="st-project">{{ s.project_name }}</span>
          <span class="pt-count">#{{ s.order }}</span>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">暂无分区</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  toolData?: Record<string, any>
  toolName?: string
}>()

const total = computed(() => props.toolData?.total ?? 0)
const sections = computed<Array<Record<string, any>>>(() => {
  const list = props.toolData?.sections
  return Array.isArray(list) ? list : []
})

const headerLabel = computed(() => {
  if (props.toolData?.project_name) return `${props.toolData.project_name} · Sections`
  return 'Sections'
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
/* ── 分区列表 ── */
.section-tree {
  display: flex;
  flex-direction: column;
}
.st-node {
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}
.st-node:last-child {
  border-bottom: none;
}
.st-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.st-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.st-project {
  font-size: 10px;
  color: var(--text-tertiary, #bbb);
  letter-spacing: 0.3px;
  border: 1px solid var(--border);
  padding: 1px 6px;
  border-radius: 2px;
}
.pt-count {
  font-size: 10px;
  color: var(--text-tertiary, #bbb);
  margin-left: auto;
  font-family: 'SF Mono', 'Consolas', monospace;
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
