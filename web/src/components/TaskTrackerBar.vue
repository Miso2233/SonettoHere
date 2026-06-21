<template>
  <div class="tracker-bar" :class="{ idle: !data }">
    <template v-if="!data">
      <span class="bar-label">无激活任务</span>
    </template>

    <template v-else>
      <span class="bar-progress-text">
        <span class="bar-num-done">{{ currentStep }}</span>
        /<span class="bar-num-total">{{ data.total }}</span>
      </span>

      <span class="bar-sep">·</span>
      <span class="bar-in-progress-label">{{ statusLabel }}</span>

      <span v-if="activeForm" class="bar-active-form">{{ activeForm }}</span>

      <span class="bar-progress-track">
        <span class="bar-progress-fill" :style="{ width: progressPercent + '%' }"></span>
      </span>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface TaskTrackerTodo {
  content: string
  status: string
  activeForm: string | null
}

interface TaskTrackerData {
  total: number
  completed: number
  in_progress?: number
  todos: TaskTrackerTodo[]
}

const props = defineProps<{ data: TaskTrackerData | null }>()

const currentStep = computed(() => {
  if (!props.data) return 0
  return props.data.completed + ((props.data.in_progress ?? 0) > 0 ? 1 : 0)
})

const progressPercent = computed(() => {
  if (!props.data || props.data.total <= 0) return 0
  return Math.round((props.data.completed / props.data.total) * 100)
})

const activeForm = computed(() => {
  if (!props.data) return ''
  const todos = props.data.todos
  if (!Array.isArray(todos)) return ''
  const current = todos.find(t => t.status === 'in_progress')
  return current?.activeForm || ''
})

const statusLabel = computed(() => {
  if (!props.data) return ''
  const todos = props.data.todos
  if (!Array.isArray(todos) || todos.length === 0) return ''

  const hasInProgress = todos.some(t => t.status === 'in_progress')
  const hasCompleted = todos.some(t => t.status === 'completed')
  const hasPending = todos.some(t => t.status === 'pending')

  if (!hasInProgress) {
    // 没有进行中的任务
    if (!hasCompleted && hasPending) return '就绪'       // 全 pending
    if (hasCompleted && !hasPending) return '已完成'      // 全 completed
    return '待命'  // 混合 pending + completed
  } else {
    // 有进行中的任务
    if (!hasCompleted) return '出发'   // 全 pending + in_progress，无 completed
    return '工作中'  // 三种状态混合
  }
})
</script>

<style scoped>
.tracker-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  font-size: 12px;
  user-select: none;
  flex-shrink: 0;
  border: 1.5px solid #0000001e;
  border-radius: 6px;
  padding: 4px 12px;
  box-shadow: var(--shadow-xs);
  transition: opacity 0.25s;
}

.tracker-bar.idle {
  opacity: 0.35;
}

.bar-label {
  font-weight: 600;
  color: #999;
}

.bar-idle {
  color: #bbb;
  font-style: italic;
}

.bar-progress-text {
  font-variant-numeric: tabular-nums;
  color: #666;
}

.bar-num-done {
  font-weight: 700;
  color: #000;
}

.bar-num-total {
  color: #999;
}

.bar-sep {
  color: #ccc;
}

.bar-in-progress-label {
  color: #000;
  font-weight: 600;
}

.bar-active-form {
  color: #666;
  font-size: 11px;
}

.bar-active-form::before {
  content: '· ';
  color: #ccc;
}

.bar-progress-track {
  width: 60px;
  height: 6px;
  background: #d0d0d0;
  border-radius: 3px;
  overflow: hidden;
  flex-shrink: 0;
  display: flex;
}

.bar-progress-fill {
  height: 100%;
  min-width: 8px;
  background: #000;
  border-radius: 3px;
  transition: width 0.3s ease;
}
</style>
