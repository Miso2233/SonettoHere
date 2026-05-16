import type { Component } from 'vue'
import BilibiliDownloadBubble from './BilibiliDownloadBubble.vue'
import TodoBubble from './TodoBubble.vue'
import TaskTrackerBubble from './TaskTrackerBubble.vue'

/** 工具注册表：tool_name → 专属气泡组件 */
const registry: Record<string, Component> = {
  'bilibili_download': BilibiliDownloadBubble,
  'todo_add': TodoBubble,
  'todo_list': TodoBubble,
  'todo_complete': TodoBubble,
  'todo_uncomplete': TodoBubble,
  'todo_delete': TodoBubble,
  'todo_update': TodoBubble,
  'todo_query': TodoBubble,
  'todo_list_projects': TodoBubble,
  'task_tracker': TaskTrackerBubble,
}

export function getBubbleComponent(name: string): Component | null {
  return registry[name] ?? null
}

export function getRegisteredTools(): string[] {
  return Object.keys(registry)
}
