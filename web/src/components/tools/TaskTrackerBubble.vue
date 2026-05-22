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

    <!-- 完成 — 有结构化数据时展示富卡片 -->
    <template v-else-if="toolCall.status === 'done'">
      <div v-if="toolCall.toolData" class="tracker-result">

        <!-- 已完成全部任务 -->
        <template v-if="toolCall.toolData.status === 'completed'">
          <div class="completed-banner">
            <span class="completed-icon">✓</span>
            <span class="completed-text">{{ toolCall.toolData.message || '所有任务已完成' }}</span>
          </div>
          <div class="completed-sub">共完成 {{ toolCall.toolData.total_steps ?? 0 }} 个步骤</div>
        </template>

        <!-- 进行中/初始化 -->
        <template v-else>
          <!-- 进度条 -->
          <div class="progress-section">
            <div class="progress-header">
              <span class="progress-label">
                步骤 {{ toolCall.toolData.current_step ?? 1 }} / {{ toolCall.toolData.total_steps ?? 0 }}
              </span>
            </div>
            <div class="progress-bar">
              <div
                class="progress-fill"
                :style="{ width: progressPercent + '%' }"
              ></div>
            </div>
          </div>

          <!-- 任务清单 -->
          <div class="task-items" v-if="(toolCall.toolData.tasks as any[])?.length">
            <div
              v-for="(task, i) in (toolCall.toolData.tasks as any[])"
              :key="i"
              class="task-row"
              :class="rowClass(i)"
            >
              <span class="step-indicator" :class="rowClass(i)">{{ stepIcon(i) }}</span>
              <span class="step-text">{{ task }}</span>
            </div>
          </div>

          <!-- 无任务列表时显示当前任务 -->
          <div v-else-if="toolCall.toolData.current_task" class="current-task-only">
            <span class="step-indicator current">→</span>
            <span class="step-text">{{ toolCall.toolData.current_task }}</span>
          </div>
        </template>

      </div>

      <!-- 无 toolData 时降级显示原始输出 -->
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

const progressPercent = computed(() => {
  const cur = (props.toolCall.toolData?.current_step as number) ?? 0
  const total = (props.toolCall.toolData?.total_steps as number) ?? 1
  if (total <= 0) return 0
  return Math.min(100, Math.round((cur / total) * 100))
})

function rowClass(i: number): string {
  const cur = (props.toolCall.toolData?.current_step as number) ?? 1
  if (i < cur - 1) return 'done'
  if (i === cur - 1) return 'current'
  return 'pending'
}

function stepIcon(i: number): string {
  const cur = (props.toolCall.toolData?.current_step as number) ?? 1
  if (i < cur - 1) return '✓'
  if (i === cur - 1) return '→'
  return '○'
}
</script>

<style scoped>
.tracker-result {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ── 进度条 ── */
.progress-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.progress-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.progress-label {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 600;
}

.progress-bar {
  height: 6px;
  background: var(--bg-primary);
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--accent);
  border-radius: 3px;
  transition: width 0.3s ease;
}

/* ── 任务清单 ── */
.task-items {
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: var(--bg-primary);
  border-radius: 6px;
  padding: 8px;
  max-height: 240px;
  overflow-y: auto;
}

.task-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 4px;
  font-size: 13px;
}

.step-indicator {
  width: 16px;
  text-align: center;
  font-size: 11px;
  flex-shrink: 0;
}

.step-indicator.done {
  color: #5a9e5a;
}

.step-indicator.current {
  color: var(--accent);
  font-weight: 700;
}

.step-indicator.pending {
  color: var(--border);
}

.step-text {
  color: var(--text-primary);
}

.task-row.done .step-text {
  color: var(--text-secondary);
  text-decoration: line-through;
}

.task-row.current .step-text {
  font-weight: 600;
  color: var(--text-primary);
}

.task-row.pending .step-text {
  color: var(--text-secondary);
}

/* ── 当前任务（无清单时） ── */
.current-task-only {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 14px;
}

/* ── 完成状态 ── */
.completed-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
}

.completed-icon {
  width: 24px;
  height: 24px;
  background: #d4e5d4;
  color: #2d5a2d;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
}

.completed-text {
  font-size: 14px;
  font-weight: 600;
  color: #2d5a2d;
}

.completed-sub {
  font-size: 12px;
  color: var(--text-secondary);
}

/* ── 降级输出 ── */
.raw-output {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  padding: 8px 12px;
  background: var(--bg-primary);
  border-radius: 6px;
}
</style>
