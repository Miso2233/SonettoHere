import type { Component } from 'vue'
import BilibiliDownloadBubble from './BilibiliDownloadBubble.vue'

/** 工具注册表：tool_name → 专属气泡组件 */
const registry: Record<string, Component> = {
  'bilibili_download': BilibiliDownloadBubble,
}

export function getBubbleComponent(name: string): Component | null {
  return registry[name] ?? null
}

export function getRegisteredTools(): string[] {
  return Object.keys(registry)
}
