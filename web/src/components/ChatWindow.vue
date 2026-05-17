<template>
  <div class="chat-window" ref="windowRef">
    <div class="messages-list">
      <!-- 已完成的消息轮次 -->
      <template v-for="turn in turns" :key="turn.id">
        <MessageBubble role="user" :content="turn.userMessage" />
        <template v-for="(ev, i) in turn.events" :key="i">
          <ThinkingBlock v-if="ev.kind === 'thinking'" :block="ev" />
          <ToolBubbleRouter v-else :tool-call="ev" @action="forwardAction" />
        </template>
        <MessageBubble
          v-if="turn.finalAnswer && !hasAnswerBlock(turn)"
          role="assistant"
          :content="turn.finalAnswer"
        />
      </template>

      <!-- 当前正在流式生成的消息 -->
      <template v-if="currentTurn">
        <MessageBubble role="user" :content="currentTurn.userMessage" />
        <template v-for="(ev, i) in currentTurn.events" :key="i">
          <ThinkingBlock v-if="ev.kind === 'thinking'" :block="ev" />
          <ToolBubbleRouter v-else :tool-call="ev" @action="forwardAction" />
        </template>
      </template>

      <!-- 错误提示 -->
      <div v-if="error" class="error-banner">{{ error }}</div>

      <!-- 空状态 -->
      <div v-if="turns.length === 0 && !currentTurn" class="empty-state">
        <p class="empty-title">SonettoHere</p>
        <p class="empty-desc">发送一条消息开始对话</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { watch, ref, nextTick } from 'vue'
import type { ChatTurn } from '@/types'
import MessageBubble from './MessageBubble.vue'
import ThinkingBlock from './ThinkingBlock.vue'
import ToolBubbleRouter from './ToolBubbleRouter.vue'

const props = defineProps<{
  turns: ChatTurn[]
  currentTurn: ChatTurn | null
  error: string | null
}>()

const emit = defineEmits<{
  (e: 'action', p: { action: string; data?: unknown }): void
}>()

function forwardAction(payload: { action: string; data?: unknown }) {
  emit('action', payload)
}

const windowRef = ref<HTMLElement | null>(null)

function hasAnswerBlock(turn: ChatTurn): boolean {
  return turn.events.some(e => e.kind === 'thinking' && e.becameAnswer)
}

function scrollToBottom() {
  nextTick(() => {
    const el = windowRef.value
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  })
}

watch(() => props.turns.length, () => scrollToBottom())
watch(
  () => props.currentTurn?.events.length,
  () => scrollToBottom()
)
watch(
  () => props.currentTurn?.finalAnswer,
  () => scrollToBottom()
)
</script>

<style scoped>
.chat-window {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
}
.messages-list {
  max-width: 768px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  gap: 8px;
}
.empty-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--accent);
}
.empty-desc {
  font-size: 14px;
  color: var(--text-secondary);
}
.error-banner {
  padding: 10px 16px;
  background: #fdeaea;
  border: 1px solid #d4a0a0;
  border-radius: var(--radius);
  color: #8b3a3a;
  font-size: 13px;
}
</style>
