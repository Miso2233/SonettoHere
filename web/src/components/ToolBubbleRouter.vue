<template>
  <component
    :is="bubbleComponent"
    v-if="bubbleComponent"
    :tool-call="toolCall"
    @action="handleAction"
  />
  <ToolCallCard v-else :tool-call="toolCall" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ToolCall } from '@/types'
import ToolCallCard from './ToolCallCard.vue'
import { getBubbleComponent } from './tools/registry'

const props = defineProps<{ toolCall: ToolCall }>()
const emit = defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

const bubbleComponent = computed(() => {
  const comp = getBubbleComponent(props.toolCall.name)
  console.log('[ToolBubbleRouter] toolCall:', {
    name: props.toolCall.name,
    status: props.toolCall.status,
    component: comp ? comp.name || 'AsyncComponent' : 'null → ToolCallCard fallback',
  })
  return comp
})

function handleAction(payload: { action: string; data?: unknown }) {
  emit('action', payload)
}
</script>
