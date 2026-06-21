<template>
  <div class="card-lineframe">
    <!-- 头部 -->
    <div class="lf-header">
      <div class="lf-header-left">
        <div class="lf-tool-label">Projects · {{ total }}</div>
        <div class="lf-timestamp">{{ nowStr }}</div>
      </div>
      <div class="lf-header-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="3" width="7" height="7" rx="1"/>
          <rect x="14" y="3" width="7" height="7" rx="1"/>
          <rect x="3" y="14" width="7" height="7" rx="1"/>
          <rect x="14" y="14" width="7" height="7" rx="1"/>
        </svg>
      </div>
    </div>

    <!-- 项目列表 -->
    <div v-if="projects.length" class="project-tree">
      <div v-for="p in projects" :key="p.project_id" class="pt-node">
        <div class="pt-project">
          <span class="pt-color-dot" :style="{ background: dotColor(p.color) }"></span>
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

/** Todoist 颜色名 → 灰度色值 */
const COLOR_MAP: Record<string, string> = {
  berry_red: '#6b7280', red: '#6b7280', orange: '#9ca3af',
  yellow: '#9ca3af', olive_green: '#9ca3af', lime_green: '#9ca3af',
  green: '#9ca3af', mint_green: '#d1d5db', teal: '#9ca3af',
  sky_blue: '#d1d5db', light_blue: '#d1d5db', blue: '#6b7280',
  grape: '#6b7280', violet: '#6b7280', lavender: '#d1d5db',
  magenta: '#6b7280', salmon: '#9ca3af', charcoal: '#333333',
  grey: '#d1d5db', taupe: '#9ca3af',
}

function dotColor(color: string | null | undefined): string {
  return COLOR_MAP[color ?? ''] ?? '#d1d5db'
}
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
.lf-header-icon {
  width: 32px;
  height: 32px;
  color: var(--text-secondary);
  flex-shrink: 0;
}
.lf-header-icon svg {
  width: 100%;
  height: 100%;
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
.pt-color-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
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
