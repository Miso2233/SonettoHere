<template>
  <BubbleChrome :tool-call="toolCall">
    <!-- 运行中 -->
    <div v-if="toolCall.status === 'running'" class="bubble-running">
      <span>正在操作 Todoist...</span>
    </div>

    <!-- 错误 -->
    <div v-else-if="toolCall.status === 'error'" class="bubble-error">
      {{ toolCall.output || '操作失败' }}
    </div>

    <!-- 完成 — 有结构化数据时展示富卡片 -->
    <template v-else-if="toolCall.status === 'done'">
      <div v-if="toolCall.toolData" class="todo-result">

        <!-- 单任务卡片 -->
        <template v-if="toolCall.toolData.tool_type === 'single_task'">
          <div class="task-card">
            <div class="task-content">
              <span class="priority-dot" :class="'p' + (toolCall.toolData.priority || 4)"></span>
              <span class="task-title">{{ toolCall.toolData.content || '未命名任务' }}</span>
            </div>
            <div class="task-meta">
              <template v-if="toolCall.toolData.due_date">
                <span class="meta-item">📅 {{ toolCall.toolData.due_date }}</span>
              </template>
              <template v-if="toolCall.toolData.project">
                <span class="meta-item">📁 {{ toolCall.toolData.project }}</span>
              </template>
              <template v-if="toolCall.toolData.is_completed !== undefined">
                <span class="meta-item status-badge" :class="toolCall.toolData.is_completed ? 'done' : 'open'">
                  {{ toolCall.toolData.is_completed ? '✓ 已完成' : '○ 未完成' }}
                </span>
              </template>
            </div>
            <div class="task-id"># {{ toolCall.toolData.task_id }}</div>
            <div v-if="toolCall.toolData.message" class="task-message">
              {{ toolCall.toolData.message }}
            </div>
          </div>
        </template>

        <!-- 任务列表 -->
        <template v-else-if="toolCall.toolData.tool_type === 'task_list'">
          <div class="list-header">共 {{ toolCall.toolData.total ?? 0 }} 个任务</div>
          <div class="task-items">
            <div
              v-for="(task, i) in (toolCall.toolData.tasks as any[])"
              :key="i"
              class="task-row"
            >
              <span class="priority-dot" :class="'p' + (task.priority || 4)"></span>
              <span class="task-row-content">{{ task.content }}</span>
              <span v-if="task.project" class="task-row-project">📁 {{ task.project }}</span>
            </div>
          </div>
          <div v-if="!(toolCall.toolData.tasks as any[])?.length" class="list-empty">
            暂无未完成任务
          </div>
        </template>

        <!-- 项目列表 -->
        <template v-else-if="toolCall.toolData.tool_type === 'project_list'">
          <div class="list-header">共 {{ toolCall.toolData.total ?? 0 }} 个项目</div>
          <div class="project-items">
            <div
              v-for="(proj, i) in (toolCall.toolData.projects as any[])"
              :key="i"
              class="project-row"
            >
              <span class="project-name">📁 {{ proj.name }}</span>
              <span class="project-id"># {{ proj.project_id }}</span>
            </div>
          </div>
          <div v-if="!(toolCall.toolData.projects as any[])?.length" class="list-empty">
            暂无项目
          </div>
        </template>

      </div>

      <!-- 无 toolData 时降级显示原始输出 -->
      <div v-else class="raw-output">{{ toolCall.output }}</div>
    </template>
  </BubbleChrome>
</template>

<script setup lang="ts">
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'

defineProps<{ toolCall: ToolCall }>()
defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()
</script>

<style scoped>
.todo-result {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* ── 单任务卡片 ── */
.task-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.task-content {
  display: flex;
  align-items: center;
  gap: 8px;
}

.task-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.meta-item {
  font-size: 12px;
  color: var(--text-secondary);
}

.status-badge {
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: 600;
}

.status-badge.done {
  background: #d4e5d4;
  color: #2d5a2d;
}

.status-badge.open {
  background: #f3f4f6;
  color: #6b7280;
}

.task-id {
  font-size: 11px;
  color: var(--text-secondary);
  font-family: 'SF Mono', 'Consolas', monospace;
  opacity: 0.7;
}

.task-message {
  font-size: 13px;
  color: #5a9e5a;
  font-weight: 500;
}

/* ── 优先级圆点 ── */
.priority-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  display: inline-block;
}

.priority-dot.p1 { background: #9e9e9e; }  /* 低 */
.priority-dot.p2 { background: #5b9bd5; }  /* 中 */
.priority-dot.p3 { background: #f4a236; }  /* 高 */
.priority-dot.p4 { background: #e44232; }  /* 紧急 */

/* ── 列表 ── */
.list-header {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 600;
  margin-bottom: 4px;
}

.task-items,
.project-items {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 240px;
  overflow-y: auto;
  background: var(--bg-primary);
  border-radius: 6px;
  padding: 8px;
}

.task-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 13px;
}

.task-row-content {
  flex: 1;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-row-project {
  font-size: 11px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.project-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 13px;
}

.project-name {
  flex: 1;
  color: var(--text-primary);
}

.project-id {
  font-size: 11px;
  color: var(--text-secondary);
  font-family: 'SF Mono', 'Consolas', monospace;
}

.list-empty {
  font-size: 12px;
  color: var(--text-secondary);
  font-style: italic;
  padding: 8px;
  text-align: center;
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
