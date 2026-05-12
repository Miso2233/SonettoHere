<template>
  <div class="chat-view">
    <header class="chat-header">
      <StatusBadge :connected="connected" />
    </header>

    <ChatWindow
      :turns="turns"
      :current-turn="currentTurn"
      :error="error"
    />

    <ChatInput
      :is-streaming="isStreaming"
      :disabled="!connected"
      @send="send"
      @stop="cancel"
    />
  </div>
</template>

<script setup lang="ts">
import { useSession } from '@/composables/useSession'
import { useChat } from '@/composables/useChat'
import StatusBadge from '@/components/StatusBadge.vue'
import ChatWindow from '@/components/ChatWindow.vue'
import ChatInput from '@/components/ChatInput.vue'

const { sessionId } = useSession()
const { connected, isStreaming, turns, currentTurn, error, send, cancel } =
  useChat(sessionId)
</script>

<style scoped>
.chat-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.chat-header {
  display: flex;
  align-items: center;
  padding: 12px 24px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-card);
}
</style>
