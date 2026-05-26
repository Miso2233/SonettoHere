<template>
  <div class="chat-view">
    <header class="chat-header">
      <StatusBadge :connected="connected" :health="health" />
      <ContextUsageBadge :usage="contextUsage" />
    </header>

    <ChatWindow
      :turns="turns"
      :current-turn="currentTurn"
      :error="error"
      @action="handleToolAction"
      @cite="addCitation"
    />

    <ChatInput
      :is-streaming="isStreaming"
      :disabled="!connected"
      :citations="citations"
      @send="onSend"
      @stop="cancel"
      @remove-citation="removeCitation"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { Citation } from '@/types'
import { useSession } from '@/composables/useSession'
import { useChat } from '@/composables/useChat'
import { health } from '@/composables/useHealth'
import StatusBadge from '@/components/StatusBadge.vue'
import ContextUsageBadge from '@/components/ContextUsageBadge.vue'
import ChatWindow from '@/components/ChatWindow.vue'
import ChatInput from '@/components/ChatInput.vue'

const { sessionId } = useSession()
const { connected, isStreaming, turns, currentTurn, error, contextUsage, send, cancel, sendUserResponse } =
  useChat(sessionId)

const citations = ref<Citation[]>([])

function addCitation(citation: Citation) {
  citations.value.push(citation)
}

function removeCitation(id: string) {
  citations.value = citations.value.filter(c => c.id !== id)
}

function onSend(message: string) {
  send(message)
  citations.value = []
}

function handleToolAction(payload: { action: string; data?: unknown }) {
  if (payload.action === 'user_response') {
    const d = payload.data as { interactionId: string; response: string | string[] }
    sendUserResponse(d.interactionId, d.response)
  }
}
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
  gap: 20px;
  padding: 12px 24px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-card);
}
</style>
