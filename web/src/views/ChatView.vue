<template>
  <div class="chat-view">
    <header class="chat-header">
      <StatusBadge :connected="connected" :health="health" />
      <span class="private-trigger hover-trigger">
        <button
          class="private-toggle"
          :class="{ active: privateMode }"
          @click="setPrivateMode(!privateMode)"
        >
          <span class="private-indicator"></span>
          {{ privateMode ? '私密' : '记忆' }}
        </button>
        <div class="hover-card card-private">
          <div class="card-row">
            <span class="card-label">私密模式</span>
            <span class="card-value" :class="privateMode ? 'status-on' : 'status-off'">
              {{ privateMode ? '已开启' : '已关闭' }}
            </span>
          </div>
          <div class="card-divider"></div>
          <div class="private-desc">
            开启后，当前对话不会被保存到长期记忆和本地存储，关闭后恢复正常保存。
          </div>
        </div>
      </span>
      <span class="auto-approve-trigger hover-trigger">
        <button
          class="auto-approve-toggle"
          :class="{ active: autoApprove }"
          @click="setAutoApprove(!autoApprove)"
        >
          <span class="auto-approve-indicator"></span>
          {{ autoApprove ? 'ATE' : 'ABE' }}
        </button>
        <div class="hover-card card-auto-approve">
          <div class="card-row">
            <span class="card-label">自动执行</span>
            <span class="card-value" :class="autoApprove ? 'status-warn' : 'status-off'">
              {{ autoApprove ? '已开启' : '已关闭' }}
            </span>
          </div>
          <div class="card-divider"></div>
          <div class="auto-approve-desc">
            {{ autoApprove ? 'Python 代码将直接执行，无需用户确认。点击切换为手动审核模式。' : 'Python 代码执行前需要您确认。点击切换为自动执行模式。' }}
          </div>
        </div>
      </span>
      <ContextUsageBadge :usage="contextUsage" :selected-model="selectedModelName" />
    </header>

    <ChatWindow
      :turns="turns"
      :current-turn="currentTurn"
      :error="error"
      @action="handleToolAction"
      @cite="addCitation"
      @toggle-private="setPrivateMode(!privateMode)"
    />

    <ChatInput
      v-if="!isSubagent"
      :is-streaming="isStreaming"
      :disabled="!connected"
      :citations="citations"
      @send="onSend"
      @stop="cancel"
      @remove-citation="removeCitation"
      @model-change="onModelChange"
    />
    <div v-else class="sub-agent-readonly-bar">
      <span class="sub-agent-readonly-text">🔒 子 Agent 会话 — 只读</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { api } from '@/api'
import ChatInput from '@/components/ChatInput.vue'
import ChatWindow from '@/components/ChatWindow.vue'
import ContextUsageBadge from '@/components/ContextUsageBadge.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import { useChat } from '@/composables/useChat'
import { health } from '@/composables/useHealth'
import { useSession } from '@/composables/useSession'
import type { Citation } from '@/types'
import type { ParsedRef } from '@/utils/references'
import { computed, ref } from 'vue'

const { sessionId, sessions } = useSession()
const { connected, isStreaming, turns, currentTurn, error, contextUsage, send, cancel, sendUserResponse, removeTurns, privateMode, setPrivateMode, autoApprove, setAutoApprove } =
  useChat(sessionId)

const selectedModelName = ref('')

function onModelChange(_providerId: string, modelName: string) {
  selectedModelName.value = modelName
}

const isSubagent = computed(() => {
  return sessions.value.some(
    s => s.session_id === sessionId.value && s.is_subagent
  )
})

const citations = ref<Citation[]>([])

function addCitation(citation: Citation) {
  citations.value.push(citation)
}

function removeCitation(id: string) {
  citations.value = citations.value.filter(c => c.id !== id)
}

function onSend(text: string, refs: ParsedRef[], providerId?: string, modelName?: string) {
  send(text, refs, providerId, modelName)
  citations.value = []
}

function handleToolAction(payload: { action: string; data?: unknown }) {
  if (payload.action === 'user_response') {
    const d = payload.data as { interactionId: string; response: string | string[] }
    sendUserResponse(d.interactionId, d.response)
  } else if (payload.action === 'undo') {
    handleUndo()
  }
}

async function handleUndo() {
  try {
    const result = await api.undoMessages(sessionId.value, 1)
    if (result.deleted_count > 0) {
      removeTurns(1)
    }
  } catch (e) {
    console.error('撤回失败:', e)
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
.private-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
}
.private-toggle:hover {
  border-color: var(--text-secondary);
}
.private-toggle.active {
  border-color: var(--status-warn);
  background: color-mix(in srgb, var(--status-warn) 10%, transparent);
  color: var(--status-warn);
}
.private-toggle:not(.active) .private-indicator {
  background: var(--accent);
}
.private-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}
.private-trigger {
  position: relative;
}
.hover-card {
  visibility: hidden;
  opacity: 0;
  transform: translateY(-4px);
  transition: visibility 0.15s ease, opacity 0.15s ease, transform 0.15s ease;
  pointer-events: none;
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  z-index: 100;
  min-width: 240px;
  padding: 8px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  font-size: 12px;
  line-height: 1.6;
}
.private-trigger:hover .hover-card {
  visibility: visible;
  opacity: 1;
  transform: translateY(0);
}
.auto-approve-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
  user-select: none;
}
.auto-approve-toggle:hover {
  border-color: var(--text-secondary);
}
/* 自动模式（autoApprove = true） */
.auto-approve-toggle.active {
  border-color: var(--status-warn);
  background: color-mix(in srgb, var(--status-warn) 10%, transparent);
  color: var(--status-warn);
}
/* 审核模式（autoApprove = false）指示器 */
.auto-approve-toggle:not(.active) .auto-approve-indicator {
  background: var(--accent);
}
.auto-approve-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}
.auto-approve-trigger {
  position: relative;
}
.auto-approve-trigger:hover .hover-card {
  visibility: visible;
  opacity: 1;
  transform: translateY(0);
}
.private-desc {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
  white-space: normal;
  max-width: 240px;
}
.status-warn {
  color: var(--status-warn);
}
.status-on {
  color: var(--status-warn);
}
.status-off {
  color: var(--text-secondary);
}
.card-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}
.card-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
}
.card-value {
  font-variant-numeric: tabular-nums;
  color: var(--text-primary);
  font-weight: 600;
}
.card-divider {
  height: 1px;
  background: var(--border);
  margin: 4px 0;
}
.auto-approve-desc {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
  white-space: normal;
  max-width: 240px;
}
.sub-agent-readonly-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px 24px;
  border-top: 1px solid var(--border);
  background: var(--bg-secondary);
}
.sub-agent-readonly-text {
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
