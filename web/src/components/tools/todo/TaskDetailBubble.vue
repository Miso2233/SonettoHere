<template>
  <div class="card-lineframe">
    <!-- 头部 -->
    <div class="lf-header">
      <div class="lf-header-left">
        <div class="lf-tool-label">Task · {{ task.content ?? 'N/A' }}</div>
        <div class="lf-timestamp">{{ projectPath }}</div>
      </div>
    </div>

    <div v-if="hasTask" class="td-grid">
      <div class="td-field">
        <div class="td-label">优先级</div>
        <div class="td-value">
          <span class="priority-inline" :class="priorityClass(task.priority)">p{{ task.priority }}</span>
          · {{ priorityLabel(task.priority) }}
        </div>
      </div>
      <div class="td-field" v-if="task.due?.date">
        <div class="td-label">截止</div>
        <div class="td-value mono">{{ task.due.date }}<span v-if="task.due.string"> · {{ task.due.string }}</span></div>
      </div>
      <div class="td-field" v-if="task.deadline?.date">
        <div class="td-label">硬期限</div>
        <div class="td-value mono">{{ task.deadline.date }}</div>
      </div>
      <div class="td-field" v-if="task.duration?.amount">
        <div class="td-label">时长</div>
        <div class="td-value mono">{{ task.duration.amount }} {{ task.duration.unit }}</div>
      </div>
      <div class="td-field">
        <div class="td-label">标签</div>
        <div class="td-value">{{ task.labels?.length ? task.labels.join(', ') : '—' }}</div>
      </div>
      <div class="td-field">
        <div class="td-label">状态</div>
        <div class="td-value">{{ task.is_completed ? '✓ 已完成' : '○ 未完成' }}</div>
      </div>
      <div class="td-field" v-if="task.creator_id">
        <div class="td-label">创建者</div>
        <div class="td-value mono">{{ task.creator_id }}</div>
      </div>
      <div class="td-field" v-if="task.parent_id">
        <div class="td-label">父任务</div>
        <div class="td-value mono">{{ task.parent_id }}</div>
      </div>
    </div>

    <!-- 描述 -->
    <div v-if="task.description" class="td-desc">
      <span class="td-label">描述</span>
      <p>{{ task.description }}</p>
    </div>

    <!-- 任务不存在 -->
    <div v-if="!hasTask && toolData && !task.content" class="empty-state">
      未找到该任务，请确认 task_id 是否正确
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ toolData?: Record<string, any> }>()

const task = computed(() => props.toolData ?? {})
const hasTask = computed(() => task.value?.content || task.value?.task_id)

const projectPath = computed(() => {
  const parts: string[] = []
  if (task.value.project_name) parts.push(task.value.project_name)
  if (task.value.section_name) parts.push(task.value.section_name)
  return parts.length ? parts.join(' / ') : '—'
})

function priorityClass(p: number | null | undefined): string {
  const map: Record<number, string> = { 1: 'p4', 2: 'p3', 3: 'p2', 4: 'p1' }
  return map[p ?? 1] ?? 'p4'
}

function priorityLabel(p: number | null | undefined): string {
  const map: Record<number, string> = { 1: '低', 2: '中', 3: '高', 4: '紧急' }
  return map[p ?? 1] ?? '低'
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
/* ── 详情网格 ── */
.td-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}
.td-field {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  font-size: 11px;
}
.td-field:nth-last-child(-n+2) {
  border-bottom: none;
}
.td-label {
  font-size: 8px;
  font-weight: 600;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--text-tertiary, #bbb);
  margin-bottom: 6px;
}
.td-value {
  color: var(--text-primary);
  font-weight: 500;
}
.td-value.mono {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 10px;
}

.priority-inline {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-weight: 600;
}
.priority-inline.p1 { color: var(--text-primary); }
.priority-inline.p2 { color: var(--text-secondary); }
.priority-inline.p3 { color: var(--text-tertiary, #9ca3af); }
.priority-inline.p4 { color: var(--text-muted, #d1d5db); }

/* ── 描述 ── */
.td-desc {
  font-size: 11px;
  color: var(--text-secondary);
}
.td-desc .td-label {
  display: block;
  margin-bottom: 4px;
}
.td-desc p {
  line-height: 1.6;
  margin: 0;
}

/* ── 空状态 ── */
.empty-state {
  text-align: center;
  padding: 24px 0;
  font-size: 12px;
  color: var(--text-secondary);
  letter-spacing: 0.3px;
}
</style>
