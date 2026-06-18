<template>
  <span class="icon" v-html="svgContent" :style="{ width: size + 'px', height: size + 'px' }"></span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import chatRaw from '@/assets/icons/sidebar/chat.svg?raw'
import memoryRaw from '@/assets/icons/sidebar/memory.svg?raw'
import modelRaw from '@/assets/icons/sidebar/model.svg?raw'
import pinRaw from '@/assets/icons/sidebar/pin.svg?raw'
import citeSpeechRaw from '@/assets/icons/context-menu/cite-speech.svg?raw'
import copyRaw from '@/assets/icons/context-menu/copy.svg?raw'
import undoArrowRaw from '@/assets/icons/context-menu/undo-arrow.svg?raw'
import attachRaw from '@/assets/icons/chat-input/attach.svg?raw'
import fileRaw from '@/assets/icons/chat-input/file.svg?raw'
import menuFileRaw from '@/assets/icons/chat-input/menu-file.svg?raw'
import menuFolderRaw from '@/assets/icons/chat-input/menu-folder.svg?raw'
import linkRaw from '@/assets/icons/chat-input/link.svg?raw'
import sparklesRaw from '@/assets/icons/chat-input/sparkles.svg?raw'
import toolRaw from '@/assets/icons/chat-input/tool.svg?raw'
import sendRaw from '@/assets/icons/chat-input/send.svg?raw'
import stopRaw from '@/assets/icons/chat-input/stop.svg?raw'

const props = withDefaults(defineProps<{
  name: string
  size?: number
}>(), {
  size: 16,
})

const svgContents: Record<string, string> = {
  chat: chatRaw,
  memory: memoryRaw,
  model: modelRaw,
  pin: pinRaw,
  settings: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="3"/>
  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
</svg>`,
  'cite-speech': citeSpeechRaw,
  copy: copyRaw,
  'undo-arrow': undoArrowRaw,
  attach: attachRaw,
  file: fileRaw,
  'menu-file': menuFileRaw,
  'menu-folder': menuFolderRaw,
  link: linkRaw,
  sparkles: sparklesRaw,
  tool: toolRaw,
  send: sendRaw,
  stop: stopRaw,
}

const svgContent = computed(() => {
  const raw = svgContents[props.name]
  if (!raw) return ''
  return raw.replace(/<\?xml[^>]*\?>/, '').trim()
})
</script>

<style scoped>
.icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  line-height: 0;
}
.icon :deep(svg) {
  width: 100%;
  height: 100%;
}
</style>
