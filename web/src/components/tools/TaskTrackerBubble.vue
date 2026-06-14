<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 运行中 -->
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>正在追踪任务...</span>
    </div>

    <!-- 错误 -->
    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '操作失败' }}
    </div>

    <!-- 完成 -->
    <template v-else-if="toolCall.status === 'done'">
      <div v-if="toolCall.toolData?.todos" class="tracker-result">

        <!-- 进度条 -->
        <div class="progress-track">
          <div class="progress-fill" :style="{ width: progressPercent + '%' }"></div>
        </div>

        <!-- 汇总 -->
        <div class="summary-line">
          <span v-if="(toolCall.toolData.completed as number) > 0" class="stat done">
            <span class="num">{{ toolCall.toolData.completed }}</span> 已完成
          </span>
          <span v-if="(toolCall.toolData.in_progress as number) > 0" class="stat current">
            <span class="num">{{ toolCall.toolData.in_progress }}</span> 进行中
            <span v-if="currentActiveForm" class="stat-active">{{ currentActiveForm }}</span>
          </span>
          <span v-if="(toolCall.toolData.pending as number) > 0" class="stat pending">
            <span class="num">{{ toolCall.toolData.pending }}</span> 待办
          </span>
          <span class="stat total">
            共 <span class="num">{{ toolCall.toolData.total }}</span> 项
          </span>
        </div>

        <!-- 待办清单 -->
        <div class="todo-items">
          <div
            v-for="(todo, i) in (toolCall.toolData.todos as any[])"
            :key="i"
            class="todo-row"
            :class="'todo-' + todo.status"
          >
            <span class="todo-icon" :class="'icon-' + todo.status">
              <template v-if="todo.status === 'completed'">✓</template>
              <template v-else-if="todo.status === 'in_progress'">→</template>
              <template v-else>○</template>
            </span>

            <span class="todo-content">{{ todo.content }}</span>
          </div>
        </div>
      </div>

      <!-- 无 todo 数据时降级输出 -->
      <div v-else class="raw-output">{{ toolCall.output }}</div>
    </template>
  </BubbleChrome>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'

const props = defineProps<{ toolCall: ToolCall }>()
defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

const currentActiveForm = computed(() => {
  const todos = props.toolCall.toolData?.todos as any[] | undefined
  if (!todos) return ''
  const current = todos.find((t: any) => t.status === 'in_progress')
  return current?.activeForm || ''
})

const progressPercent = computed(() => {
  const data = props.toolCall.toolData
  if (!data) return 0
  const total = (data.total as number) ?? 0
  const done = (data.completed as number) ?? 0
  if (total <= 0) return 0
  return Math.min(100, Math.round((done / total) * 100))
})
</script>

<style scoped>
.tracker-result {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ── 黑白进度条 ── */
.progress-track {
  height: 4px;
  background: #e0e0e0;
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #000;
  border-radius: 2px;
  transition: width 0.3s ease;
}

/* ── 汇总行 ── */
.summary-line {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 12px;
  padding: 4px 0;
}

.stat {
  color: #999;
}

.stat .num {
  font-variant-numeric: tabular-nums;
}

.stat.done .num {
  font-weight: 700;
  color: #000;
}

.stat.current {
  font-weight: 600;
  color: #000;
}

.stat.current .num {
  color: #000;
}

.stat.total {
  margin-left: auto;
  color: #ccc;
}

.stat-active {
  margin-left: 4px;
  font-weight: 400;
  color: #666;
  font-size: 11px;
}

.stat-active::before {
  content: '· ';
}

/* ── 待办清单 ── */
.todo-items {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 0;
}

.todo-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 4px;
  font-size: 13px;
  border-bottom: 1px solid #f0f0f0;
}

.todo-row:last-child {
  border-bottom: none;
}

/* ── 状态图标 ── */
.todo-icon {
  width: 18px;
  text-align: center;
  font-size: 12px;
  flex-shrink: 0;
}

.icon-completed {
  color: #999;
  font-weight: 400;
}

.icon-in_progress {
  color: #000;
  font-weight: 700;
}

.icon-pending {
  color: #ccc;
}

/* ── 任务内容 ── */
.todo-completed .todo-content {
  color: #bbb;
  text-decoration: line-through;
}

.todo-in_progress .todo-content {
  font-weight: 600;
  color: #000;
}

.todo-pending .todo-content {
  color: #999;
}

/* ── 降级输出 ── */
.raw-output {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  color: #333;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  padding: 8px 12px;
  background: #f8f8f8;
  border-radius: 4px;
}

.bubble-running {
  color: #666;
  font-size: 13px;
}

.bubble-error {
  color: #c00;
  font-size: 13px;
}
</style>
