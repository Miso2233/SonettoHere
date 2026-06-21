<template>
  <div class="card-lineframe">
    <!-- 头部 -->
    <div class="lf-header">
      <div class="lf-header-left">
        <div class="lf-tool-label">Projects · {{ total }}</div>
        <div class="lf-timestamp">{{ nowStr }}</div>
      </div>
    </div>

    <!-- 项目列表 -->
    <div v-if="projects.length" class="project-tree">
      <div v-for="p in projects" :key="p.project_id" class="pt-node">
        <div class="pt-project">
          <span class="pt-name">{{ p.name }}</span>
          <span v-if="p.is_inbox_project" class="pt-badge">INBOX</span>
          <span class="pt-count">{{ p.view_style === 'board' ? 'board' : 'list' }}</span>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">暂无项目</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ toolData?: Record<string, any> }>()

const total = computed(() => props.toolData?.total ?? 0)
const projects = computed<Array<Record<string, any>>>(() => {
  const list = props.toolData?.projects
  return Array.isArray(list) ? list : []
})

const nowStr = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
})

</script>

<style scoped>
/* ── 线框卡片 ── */
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
/* ── 项目树 ── */
.project-tree {
  display: flex;
  flex-direction: column;
}
.pt-node {
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}
.pt-node:last-child {
  border-bottom: none;
}
.pt-project {
  display: flex;
  align-items: center;
  gap: 10px;
}
.pt-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.pt-badge {
  font-size: 9px;
  font-weight: 600;
  letter-spacing: 0.5px;
  color: var(--text-tertiary, #bbb);
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
