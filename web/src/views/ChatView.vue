<template>
  <div class="chat-view">
    <!-- 无提供商引导卡片 -->
    <div v-if="!hasProviders" class="no-provider-overlay">
      <div class="no-provider-card">
        <div class="no-provider-icon">⚙️</div>
        <h3>暂无已配置的 LLM 提供商</h3>
        <p>请添加一个 API 提供商以开始对话。SonettoHere 支持任何 OpenAI 兼容 API。</p>
        <router-link to="/providers" class="btn primary">前往模型设置</router-link>
      </div>
    </div>
    <!-- 正常聊天界面 -->
    <template v-else>
    <header class="chat-header">
        <StatusBadge :connected="connected" :health="health" />
        <ContextUsageBadge :usage="contextUsage" :selected-model="selectedModelName" />
        <TaskTrackerBar :data="taskTrackerData as any" />
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
      ref="chatInputRef"
      :is-streaming="isStreaming"
      :disabled="!connected"
      :private-mode="privateMode"
      :auto-approve="autoApprove"
      @send="onSend"
      @stop="cancel"
      @model-change="onModelChange"
      @toggle-private="setPrivateMode(!privateMode)"
      @toggle-auto-approve="setAutoApprove(!autoApprove)"
    />
    <div v-else class="sub-agent-readonly-bar">
      <span class="sub-agent-readonly-text">🔒 子 Agent 会话 — 只读</span>
    </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { api } from '@/api'
import ChatInput from '@/components/ChatInput.vue'
import ChatWindow from '@/components/ChatWindow.vue'
import ContextUsageBadge from '@/components/ContextUsageBadge.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import TaskTrackerBar from '@/components/TaskTrackerBar.vue'
import { useChat } from '@/composables/useChat'
import { health } from '@/composables/useHealth'
import { useSession } from '@/composables/useSession'
import type { ParsedRef } from '@/utils/references'
import { computed, onMounted, ref } from 'vue'

const { sessionId, sessions } = useSession()
const { connected, isStreaming, turns, currentTurn, error, contextUsage, taskTrackerData, send, cancel, sendUserResponse, removeTurns, privateMode, setPrivateMode, autoApprove, setAutoApprove } =
  useChat(sessionId)

const selectedModelName = ref('')
const hasProviders = ref(true)

onMounted(async () => {
  try {
    const res = await api.listProviders()
    hasProviders.value = res.providers.some(p => p.enabled)
  } catch {
    hasProviders.value = true // fallback: assume there's a provider
  }
})

function onModelChange(_providerId: string, modelName: string) {
  selectedModelName.value = modelName
}

const isSubagent = computed(() => {
  return sessions.value.some(
    s => s.session_id === sessionId.value && s.is_subagent
  )
})

const chatInputRef = ref<InstanceType<typeof ChatInput> | null>(null)

function addCitation(ref: ParsedRef) {
  chatInputRef.value?.addRef(ref)
}

function onSend(text: string, refs: ParsedRef[], providerId?: string, modelName?: string, imageRecognition?: boolean, imagePaths?: string[]) {
  send(text, refs, providerId, modelName, imageRecognition, imagePaths)
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

/* ── 无提供商引导 ── */
.no-provider-overlay {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}
.no-provider-card {
  text-align: center;
  max-width: 400px;
  padding: 40px 32px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: var(--shadow-sm);
}
.no-provider-icon {
  font-size: 48px;
  margin-bottom: 16px;
}
.no-provider-card h3 {
  font-size: 18px;
  font-weight: 700;
  margin: 0 0 8px;
  color: var(--text-primary);
}
.no-provider-card p {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin: 0 0 24px;
}
.btn.primary {
  display: inline-block;
  padding: 10px 24px;
  background: var(--accent);
  color: #fff;
  border-radius: 8px;
  text-decoration: none;
  font-size: 14px;
  font-weight: 600;
  transition: opacity 0.15s;
}
.btn.primary:hover {
  opacity: 0.85;
}

</style>
