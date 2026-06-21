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

    <!-- 完成 -->
    <template v-else-if="toolCall.status === 'done'">
      <ProjectTreeBubble
        v-if="toolCall.name === 'todo_list_projects'"
        :toolData="parsedData"
      />
      <SectionListBubble
        v-else-if="toolCall.name === 'todo_list_sections'"
        :toolData="parsedData"
        :toolName="toolCall.name"
      />
      <LabelListBubble
        v-else-if="toolCall.name === 'todo_list_labels'"
        :toolData="parsedData"
      />
      <TaskListBubble
        v-else-if="toolCall.name === 'todo_list'"
        :toolData="parsedData"
        :headerOverride="listHeader"
      />
      <TaskDetailBubble
        v-else-if="toolCall.name === 'todo_query'"
        :toolData="parsedData"
      />
      <ActionResultBubble
        v-else-if="isActionResult"
        :toolName="toolCall.name"
        :toolData="parsedData"
      />

      <!-- 兜底：纯文本输出 -->
      <div v-else class="raw-output">{{ rawText }}</div>
    </template>
  </BubbleChrome>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ToolCall } from '@/types'
import BubbleChrome from './_shared/BubbleChrome.vue'
import ProjectTreeBubble from './todo/ProjectTreeBubble.vue'
import TaskListBubble from './todo/TaskListBubble.vue'
import TaskDetailBubble from './todo/TaskDetailBubble.vue'
import ActionResultBubble from './todo/ActionResultBubble.vue'
import SectionListBubble from './todo/SectionListBubble.vue'
import LabelListBubble from './todo/LabelListBubble.vue'

const props = defineProps<{ toolCall: ToolCall }>()
defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

const actionTools = new Set([
  'todo_add', 'todo_add_quick', 'todo_update',
  'todo_complete', 'todo_uncomplete', 'todo_delete',
])

const isActionResult = computed(() => actionTools.has(props.toolCall.name))

/** 解析 toolData 或 output */
const parsedData = computed<Record<string, any>>(() => {
  if (props.toolCall.toolData) return props.toolCall.toolData as Record<string, any>
  if (props.toolCall.output) {
    try {
      const p = JSON.parse(props.toolCall.output)
      if (p?.data) return p.data as Record<string, any>
    } catch { /* ignore */ }
  }
  return {}
})

/** 用于 todo_list 的项目名上下文 */
const listHeader = computed(() => {
  if (!props.toolCall.input) return undefined
  try {
    const input = typeof props.toolCall.input === 'string'
      ? JSON.parse(props.toolCall.input)
      : props.toolCall.input
    return input.project_name || undefined
  } catch {
    return undefined
  }
})

/** 兜底原始文本 */
const rawText = computed(() => {
  if (props.toolCall.output) {
    return props.toolCall.output.length > 800
      ? props.toolCall.output.slice(0, 800) + '...'
      : props.toolCall.output
  }
  return null
})
</script>

<style scoped>
.bubble-running {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  font-size: 13px;
  color: var(--text-secondary);
}
.bubble-error {
  font-size: 13px;
  color: #b91c1c;
  padding: 4px 0;
}
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
