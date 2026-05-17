<template>
  <div class="tool-bubble" :class="[toolCall.status, { open: isOpen }]">
    <div class="bubble-header" @click="toggle" role="button" :aria-expanded="isOpen">
      <span class="bubble-status">
        <span v-if="toolCall.status === 'running'" class="spinner"></span>
        <span v-else-if="toolCall.status === 'done'">&#10003;</span>
        <span v-else>&#10007;</span>
      </span>
      <span class="bubble-name">{{ displayName }}</span>
      <span class="bubble-elapsed" v-if="toolCall.elapsed !== null">
        {{ toolCall.elapsed }}s
      </span>
    </div>
    <div class="bubble-body-wrapper" ref="bodyWrapper">
      <div class="bubble-body" ref="bodyInner">
        <slot></slot>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import type { ToolCall } from '@/types'
import { toolDisplayName } from './displayNames'

const props = defineProps<{ toolCall: ToolCall }>()

const isOpen = ref(false)
const bodyWrapper = ref<HTMLElement | null>(null)

const displayName = computed(() => toolDisplayName(props.toolCall.name))

function toggle() {
  if (props.toolCall.status === 'running') return
  isOpen.value = !isOpen.value
}

watch(isOpen, (open) => {
  if (!bodyWrapper.value) return
  if (open) {
    // Capture current scroll height to animate the open
    const h = bodyWrapper.value.scrollHeight
    bodyWrapper.value.style.maxHeight = h + 'px'
    // After animation completes, remove constraint so expandable content can grow
    setTimeout(() => {
      if (bodyWrapper.value && isOpen.value) {
        bodyWrapper.value.style.maxHeight = 'none'
      }
    }, 350) // slightly longer than CSS transition (0.3s)
  } else {
    // Freeze at current height for smooth collapse
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

// expose nothing — parent controls via toolCall prop changes
</script>

<style scoped>
</style>
