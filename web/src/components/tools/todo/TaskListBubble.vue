<template>
  <div class="card-lineframe">
    <!-- 头部 -->
    <div class="lf-header">
      <div class="lf-header-left">
        <div class="lf-tool-label">{{ headerLabel }}</div>
        <div class="lf-timestamp">{{ total }} tasks</div>
      </div>
    </div>

    <!-- 任务列表 -->
    <div v-if="tasks.length" class="task-list">
      <div v-for="t in tasks" :key="t.task_id" class="tl-row">
        <span class="tl-priority" :class="priorityClass(t.priority)">p{{ t.priority }}</span>
        <span class="tl-content" :class="{ done: t.is_completed }">{{ t.content }}</span>
        <span v-if="t.section_name" class="tl-section">{{ t.section_name }}</span>
        <span v-if="dueText(t)" class="tl-due">{{ dueText(t) }}</span>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">暂无待办任务</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  toolData?: Record<string, any>
  headerOverride?: string
}>()

const total = computed(() => props.toolData?.total ?? 0)
const tasks = computed<Array<Record<string, any>>>(() => {
  const list = props.toolData?.tasks
  return Array.isArray(list) ? list : []
})

const headerLabel = computed(() => {
  if (props.headerOverride) return props.headerOverride
  if (props.toolData?.project_name) return props.toolData.project_name
  if (props.toolData?.section_name) return `${props.toolData.project_name ?? ''} · ${props.toolData.section_name}`
  return 'Tasks'
})

/** Todoist priority 1=低 → p4, 4=紧急 → p1 */
function priorityClass(p: number | null | undefined): string {
  const map: Record<number, string> = { 1: 'p4', 2: 'p3', 3: 'p2', 4: 'p1' }
  return map[p ?? 1] ?? 'p4'
}

function dueText(t: Record<string, any>): string | null {
  if (!t.due?.date) return null
  const d = String(t.due.date)
  // 只显示月-日 时:分
  const m = d.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (m) {
    const time = t.due.string?.match(/\d{1,2}:\d{2}/)?.[0]
    return `${m[2]}-${m[3]}${time ? ' ' + time : ''}`
  }
  return d
}
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
/* ── 任务列表 ── */
.task-list {
  display: flex;
  flex-direction: column;
}
.tl-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}
.tl-row:last-child {
  border-bottom: none;
}
.tl-priority {
  font-size: 9px;
  font-weight: 600;
  font-family: 'SF Mono', 'Consolas', monospace;
  color: var(--text-tertiary, #bbb);
  width: 18px;
  flex-shrink: 0;
  letter-spacing: 0;
}
.tl-priority.p1 { color: var(--text-primary); }
.tl-priority.p2 { color: var(--text-secondary); }
.tl-priority.p3 { color: var(--text-tertiary, #9ca3af); }
.tl-priority.p4 { color: var(--text-muted, #d1d5db); }
.tl-content {
  flex: 1;
  font-size: 12px;
  color: var(--text-primary);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tl-content.done {
  text-decoration: line-through;
  color: var(--text-tertiary, #9ca3af);
}
.tl-section {
  font-size: 9px;
  color: var(--text-tertiary, #bbb);
  letter-spacing: 0.3px;
  border: 1px solid var(--border);
  padding: 1px 6px;
  border-radius: 2px;
  text-transform: uppercase;
  flex-shrink: 0;
}
.tl-due {
  font-size: 10px;
  color: var(--text-secondary);
  font-family: 'SF Mono', 'Consolas', monospace;
  flex-shrink: 0;
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
