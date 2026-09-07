<template>
  <!-- 确认门控：任何等待用户（awaiting_user）且 mode∈{confirm, sudo} 且未提交的
       工具，统一渲染共享 ConfirmBubble 单文件（sudo 以红调标签区分） -->
  <ConfirmBubble
    v-if="isConfirmPending"
    :tool-call="toolCall"
    @action="handleAction"
  />
  <!-- 后台 spawn 门控：background=true 的调用立即返回索引（无业务结果），
       专属气泡拿到空 toolData 会渲染成空框架，统一渲染后台卡片 -->
  <BackgroundSpawnCard
    v-else-if="isBackgroundSpawn"
    :tool-call="toolCall"
  />
  <component
    :is="bubbleComponent"
    v-else-if="bubbleComponent"
    :tool-call="toolCall"
    @action="handleAction"
  />
  <ToolCallCard v-else :tool-call="toolCall" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ToolCall } from '@/types'
import ToolCallCard from './ToolCallCard.vue'
import ConfirmBubble from './tools/_shared/ConfirmBubble.vue'
import BackgroundSpawnCard from './tools/_shared/BackgroundSpawnCard.vue'
import { getBubbleComponent } from './tools/registry'

const props = defineProps<{ toolCall: ToolCall }>()
const emit = defineEmits<{ (e: 'action', p: { action: string; data?: unknown }): void }>()

/**
 * 确认门控条件：等待用户（awaiting_user）+ 确认类交互（confirm/sudo 统一走
 * 同一个共享 ConfirmBubble 单文件）+ 用户尚未回应。
 */
const CONFIRM_MODES = ['confirm', 'sudo']
const isConfirmPending = computed(() => {
  const it = props.toolCall.interaction
  return props.toolCall.status === 'awaiting_user'
    && it != null
    && !it.submitted
    && CONFIRM_MODES.includes(it.mode)
})

/**
 * 后台 spawn 门控：background=true 的调用气泡本身已 done（返回值只有任务
 * 索引信封，无业务数据），统一渲染后台卡片；后台任务的终态由徽章体现。
 */
const isBackgroundSpawn = computed(() =>
  props.toolCall.status === 'done' && !!props.toolCall.background
)

const bubbleComponent = computed(() => {
  const comp = getBubbleComponent(props.toolCall.name)
  console.log('[ToolBubbleRouter] toolCall:', {
    name: props.toolCall.name,
    status: props.toolCall.status,
    mode: props.toolCall.interaction?.mode,
    submitted: props.toolCall.interaction?.submitted,
    component: comp ? comp.name || 'AsyncComponent' : 'null → ToolCallCard fallback',
  })
  return comp
})

function handleAction(payload: { action: string; data?: unknown }) {
  emit('action', payload)
}
</script>
