<template>
  <div class="card-lineframe">
    <!-- 头部 -->
    <div class="lf-header">
      <div class="lf-header-left">
        <div class="lf-tool-label">{{ actionLabel }}</div>
        <div class="lf-timestamp">{{ nowStr }}</div>
      </div>
    </div>

    <div class="action-result">
      <div class="ar-text">
        <div class="ar-title" :class="{ done: isCompleteAction }">{{ taskTitle }}</div>
        <div class="ar-detail">{{ actionDetail }}</div>
      </div>
      <div v-if="prioritySuffix" class="ar-time">{{ prioritySuffix }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  toolName: string
  toolData?: Record<string, any>
}>()

const task = computed(() => props.toolData ?? {})

const actionType = computed(() => {
  const n = props.toolName
  if (n === 'todo_add' || n === 'todo_add_quick') return 'create'
  if (n === 'todo_complete') return 'complete'
  if (n === 'todo_uncomplete') return 'uncomplete'
  if (n === 'todo_delete') return 'delete'
  if (n === 'todo_update') return 'update'
  return 'unknown'
})

const actionLabel = computed(() => {
  const m: Record<string, string> = {
    create: 'Task Created',
    complete: 'Task Completed',
    uncomplete: 'Task Reopened',
    delete: 'Task Deleted',
    update: 'Task Updated',
    unknown: 'Task',
  }
  return m[actionType.value]
})

const nowStr = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
})

const taskTitle = computed(() => task.value.content ?? '未命名任务')

const isCompleteAction = computed(() =>
  actionType.value === 'complete' || actionType.value === 'delete'
)

const actionDetail = computed(() => {
  const t = task.value
  switch (actionType.value) {
    case 'create': {
      const parts: string[] = []
      if (t.project_name) parts.push(t.project_name)
      if (t.section_name) parts.push(t.section_name)
      const path = parts.length ? parts.join(' → ') : ''
      const due = t.due?.date ?? ''
      return [path, due].filter(Boolean).join(' · ')
    }
    case 'complete':
      return '已完成'
    case 'uncomplete':
      return '已重新打开'
    case 'delete': {
      const parts: string[] = []
      if (t.project_name) parts.push(t.project_name)
      if (t.section_name) parts.push(t.section_name)
      const path = parts.length ? `已从 ${parts.join(' / ')} 中移除` : '已删除'
      const due = t.due?.date ? `原到期 ${t.due.date}` : ''
      return [path, due].filter(Boolean).join(' · ')
    }
    case 'update':
      return '已更新'
    default:
      return ''
  }
})

const prioritySuffix = computed(() => {
  if (actionType.value !== 'create') return ''
  const p = task.value.priority
  if (!p) return ''
  const d = task.value.duration
  const dur = d?.amount ? `${d.amount}${d.unit === 'day' ? 'd' : 'min'}` : ''
  return [`p${p}`, dur].filter(Boolean).join(' ')
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
/* ── 操作结果 ── */
.action-result {
  display: flex;
  align-items: center;
  gap: 12px;
}
.ar-text {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  min-width: 0;
}
.ar-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ar-title.done {
  text-decoration: line-through;
  color: var(--text-tertiary, #9ca3af);
}
.ar-detail {
  font-size: 11px;
  color: var(--text-secondary);
}
.ar-time {
  font-size: 10px;
  color: var(--text-tertiary, #bbb);
  font-family: 'SF Mono', 'Consolas', monospace;
  flex-shrink: 0;
}
</style>
