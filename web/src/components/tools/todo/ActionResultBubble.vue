<template>
  <div class="card-lineframe">
    <!-- 头部 -->
    <div class="lf-header">
      <div class="lf-header-left">
        <div class="lf-tool-label">{{ actionLabel }}</div>
        <div class="lf-timestamp">{{ nowStr }}</div>
      </div>
      <div class="lf-header-icon" v-html="actionSvg"></div>
    </div>

    <div class="action-result">
      <div class="ar-icon">{{ actionIcon }}</div>
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

const actionIcon = computed(() => {
  const m: Record<string, string> = {
    create: '+',
    complete: '✓',
    uncomplete: '↩',
    delete: '✕',
    update: '✎',
    unknown: '•',
  }
  return m[actionType.value]
})

const actionSvg = computed(() => {
  const m: Record<string, string> = {
    create: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="10"/><polyline points="8,12 11,15 16,9"/>
    </svg>`,
    complete: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="10"/><polyline points="8,12 11,15 16,9"/>
    </svg>`,
    uncomplete: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="10"/><polyline points="12,8 12,16 8,12 16,12"/>
    </svg>`,
    delete: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="10"/><line x1="8" y1="8" x2="16" y2="16"/><line x1="16" y1="8" x2="8" y2="16"/>
    </svg>`,
    update: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
      <path d="M17 2l4 4-14 14-4-4z"/><line x1="15" y1="6" x2="18" y2="9"/>
    </svg>`,
    unknown: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
    </svg>`,
  }
  return m[actionType.value] ?? m.unknown
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

/* ── 操作结果 ── */
.action-result {
  display: flex;
  align-items: center;
  gap: 12px;
}
.ar-icon {
  width: 28px;
  height: 28px;
  border: 1.5px solid var(--text-primary);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-primary);
  font-size: 14px;
  flex-shrink: 0;
}
.ar-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
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
