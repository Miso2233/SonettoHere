<template>
  <div class="tool-card" :class="[toolCall.status, { open: isOpen }]">
    <div class="tool-header" @click="toggle" role="button" :aria-expanded="isOpen">
      <span class="tool-icon">
        <span v-if="toolCall.status === 'running'" class="spinner-sm"></span>
        <span v-else-if="toolCall.status === 'done'">&#10003;</span>
        <span v-else>&#10007;</span>
      </span>
      <span class="tool-name">{{ toolCall.name }}</span>
      <span class="tool-elapsed" v-if="toolCall.elapsed !== null">
        {{ toolCall.elapsed }}s
      </span>
    </div>
    <div class="tool-body-wrapper" ref="bodyWrapper">
      <div class="tool-body" ref="bodyInner">
        <div class="tool-section" v-if="toolCall.input && toolCall.input !== '{}'">
          <div class="tool-section-label">参数</div>
          <div class="markdown-body" v-html="renderedInput"></div>
        </div>
        <div class="tool-section" v-if="toolCall.output">
          <div class="tool-section-label">结果</div>
          <div class="markdown-body" v-html="renderedOutput"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue'
import type { ToolCall } from '@/types'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps<{ toolCall: ToolCall }>()

const isOpen = ref(false)
const bodyWrapper = ref<HTMLElement | null>(null)
const bodyInner = ref<HTMLElement | null>(null)

const renderedInput = computed(() => renderMarkdown(props.toolCall.input))
const renderedOutput = computed(() => renderMarkdown(props.toolCall.output ?? ''))

function toggle() {
  if (props.toolCall.status === 'running') return
  isOpen.value = !isOpen.value
}

watch(isOpen, (open) => {
  if (!bodyWrapper.value) return
  if (open) {
    bodyWrapper.value.style.maxHeight = bodyWrapper.value.scrollHeight + 'px'
  } else {
    bodyWrapper.value.style.maxHeight = bodyWrapper.value.scrollHeight + 'px'
    void bodyWrapper.value.offsetHeight
    bodyWrapper.value.style.maxHeight = '0px'
  }
})

watch(() => props.toolCall.status, (s) => {
  if (s === 'running') {
    isOpen.value = true
  }
})

watch(() => props.toolCall.output, () => {
  nextTick(() => {
    if (isOpen.value && bodyWrapper.value) {
      bodyWrapper.value.style.maxHeight = bodyWrapper.value.scrollHeight + 'px'
    }
  })
})
</script>

<style scoped>
.tool-card {
  margin: 8px 0;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-card);
  overflow: hidden;
}
.tool-card.running {
  border-color: var(--accent-light);
}
.tool-card.error {
  border-color: #d4a0a0;
}
.tool-header {
  padding: 8px 14px;
  font-size: 13px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}
.tool-icon {
  font-size: 12px;
  width: 16px;
  text-align: center;
}
.spinner-sm {
  display: inline-block;
  width: 10px;
  height: 10px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.tool-name {
  font-weight: 600;
  color: var(--text-primary);
}
.tool-elapsed {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-secondary);
}
.tool-body-wrapper {
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.3s cubic-bezier(0, 0.3, 0, 1);
}
.tool-body {
  border-top: 1px solid var(--border);
  padding: 8px 14px 12px;
}
.tool-section {
  margin-bottom: 8px;
}
.tool-section:last-child {
  margin-bottom: 0;
}
.tool-section-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* ── Compact markdown code blocks inside tool cards ── */
.tool-section :deep(.markdown-body) {
  font-size: 13px;
  line-height: 1.5;
}
.tool-section :deep(.markdown-body pre) {
  font-size: 12px;
  padding: 8px;
  border-radius: 6px;
  margin: 4px 0;
  max-height: 200px;
  overflow-y: auto;
  background: var(--bg-primary);
}
.tool-section :deep(.markdown-body code) {
  font-size: 12px;
}
.tool-section :deep(.markdown-body) > *:first-child {
  margin-top: 0;
}
.tool-section :deep(.markdown-body) > *:last-child {
  margin-bottom: 0;
}
</style>
