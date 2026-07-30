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
        <div v-if="imageRecognition || privateMode || skipRecall || autoApprove" class="header-mode-tags">
          <span v-if="imageRecognition" class="mode-tag">
            <svg class="mode-tag-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
            图像认知
          </span>
          <span v-if="privateMode" class="mode-tag">
            <svg class="mode-tag-icon" viewBox="0 0 82.118 82.118" fill="currentColor"><path d="M75.346,15.559h-47.9c-3.499,0-4.873,1.509-6.328,2.905c-0.294,0.283-0.613,0.685-0.982,1.01c-0.045,0.04-0.088,0.128-0.129,0.172L0.548,40.216c-0.721,0.761-0.731,1.962-0.024,2.737l19.459,21.298c0.07,0.076,0.146-0.04,0.227,0.024c2.194,1.756,3.463,2.284,7.237,2.284h47.899c4.35,0,6.772-2.659,6.772-7.184V24.2C82.118,19.491,79.491,15.559,75.346,15.559z M78.118,59.375c0,1.331,0.075,3.184-2.772,3.184h-47.9c-2.675,0-3.106-0.101-4.616-1.307L4.731,41.544L22.85,22.461c0.387-0.344,0.725-0.833,1.037-1.134c1.281-1.229,1.668-1.767,3.559-1.767h47.899c2.248,0,2.772,2.589,2.772,4.641v35.174H78.118z M26.143,34.135c-4.297,0-7.793,3.496-7.793,7.794c0,4.297,3.496,7.793,7.793,7.793s7.793-3.496,7.793-7.793C33.936,37.631,30.44,34.135,26.143,34.135z M26.143,45.722c-2.092,0-3.793-1.701-3.793-3.793s1.701-3.794,3.793-3.794s3.793,1.702,3.793,3.794S28.235,45.722,26.143,45.722z"/></svg>
            私密
          </span>
          <span v-if="skipRecall" class="mode-tag">
            <svg class="mode-tag-icon" viewBox="0 0 82.118 82.118" fill="currentColor"><path d="M75.346,15.559h-47.9c-3.499,0-4.873,1.509-6.328,2.905c-0.294,0.283-0.613,0.685-0.982,1.01c-0.045,0.04-0.088,0.128-0.129,0.172L0.548,40.216c-0.721,0.761-0.731,1.962-0.024,2.737l19.459,21.298c0.07,0.076,0.146-0.04,0.227,0.024c2.194,1.756,3.463,2.284,7.237,2.284h47.899c4.35,0,6.772-2.659,6.772-7.184V24.2C82.118,19.491,79.491,15.559,75.346,15.559z M78.118,59.375c0,1.331,0.075,3.184-2.772,3.184h-47.9c-2.675,0-3.106-0.101-4.616-1.307L4.731,41.544L22.85,22.461c0.387-0.344,0.725-0.833,1.037-1.134c1.281-1.229,1.668-1.767,3.559-1.767h47.899c2.248,0,2.772,2.589,2.772,4.641v35.174H78.118z M26.143,34.135c-4.297,0-7.793,3.496-7.793,7.794c0,4.297,3.496,7.793,7.793,7.793s7.793-3.496,7.793-7.793C33.936,37.631,30.44,34.135,26.143,34.135z M26.143,45.722c-2.092,0-3.793-1.701-3.793-3.793s1.701-3.794,3.793-3.794s3.793,1.702,3.793,3.794S28.235,45.722,26.143,45.722z"/></svg>
            失忆
          </span>
          <span v-if="autoApprove" class="mode-tag">
            <svg class="mode-tag-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
            自动执行
          </span>
        </div>
        <ContextUsageBadge :usage="contextUsage" :selected-model="selectedModelName" :has-vision="selectedModelHasVision" />
        <TaskTrackerBar :data="taskTrackerData as any" @dismiss="dismissTaskTracker" />
    </header>

    <ChatWindow
      :turns="turns"
      :current-turn="currentTurn"
      :error="error"
      @action="handleToolAction"
      @cite="addCitation"
      @toggle-private="setPrivateMode(!privateMode)"
      @toggle-recall="setSkipRecall(!skipRecall)"
    />

    <ChatInput
      v-if="!isSubagent"
      ref="chatInputRef"
      :is-streaming="isStreaming"
      :disabled="!connected"
      :private-mode="privateMode"
      :skip-recall="skipRecall"
      :auto-approve="autoApprove"
      :image-recognition="imageRecognition"
      :has-vision="selectedModelHasVision"
      @send="onSend"
      @stop="cancel"
      @model-change="onModelChange"
      @toggle-private="setPrivateMode(!privateMode)"
      @toggle-recall="setSkipRecall(!skipRecall)"
      @toggle-auto-approve="setAutoApprove(!autoApprove)"
      @toggle-image-recognition="imageRecognition = !imageRecognition"
    />
    <div v-else class="sub-agent-bar-wrapper">
      <div class="sub-agent-bar">
        <div class="sub-agent-bar-left">
          <button
            class="sub-agent-btn-check"
            :class="{ active: autoApprove }"
            :title="autoApprove ? '自动执行：Python 代码将直接执行' : '审核模式：代码执行前需确认'"
            @click="setAutoApprove(!autoApprove)"
          >
            <Icon name="code" :size="14" />
          </button>
          <span class="sub-agent-task" :title="currentTurn?.userMessage">
            {{ taskPreview }}
          </span>
        </div>
        <div class="sub-agent-bar-right">
          <span class="sub-agent-meta">#{{ sessionId?.slice(0, 8) }}</span>
        </div>
      </div>
    </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { api } from '@/api'
import ChatInput from '@/components/ChatInput.vue'
import ChatWindow from '@/components/ChatWindow.vue'
import Icon from '@/components/Icon.vue'
import ContextUsageBadge from '@/components/ContextUsageBadge.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import TaskTrackerBar from '@/components/TaskTrackerBar.vue'
import { useChat } from '@/composables/useChat'
import { useChatStore } from '@/stores/chatStore'
import { health } from '@/composables/useHealth'
import { useSession } from '@/composables/useSession'
import type { ParsedRef } from '@/utils/references'
import type { ProviderConfig } from '@/types'
import { computed, onMounted, ref } from 'vue'

const { sessionId, sessions } = useSession()
const { connected, isStreaming, turns, currentTurn, error, contextUsage, taskTrackerData, send, cancel, sendUserResponse, removeTurns, privateMode, setPrivateMode, skipRecall, setSkipRecall, autoApprove, setAutoApprove } =
  useChat(sessionId)
const chatStore = useChatStore()

function dismissTaskTracker() {
  const ch = chatStore.getOrCreateChannel(sessionId.value)
  ch.taskTrackerData = null
}

const selectedModelName = ref('')
const selectedProviderId = ref('')
const providers = ref<ProviderConfig[]>([])
const hasProviders = ref(true)
const imageRecognition = ref(false)

onMounted(async () => {
  try {
    const res = await api.listProviders()
    providers.value = res.providers
    hasProviders.value = res.providers.some(p => p.enabled)
  } catch {
    hasProviders.value = true // fallback: assume there's a provider
  }
})

function onModelChange(providerId: string, modelName: string) {
  selectedProviderId.value = providerId
  selectedModelName.value = modelName
}

const isSubagent = computed(() => {
  return sessions.value.some(
    s => s.session_id === sessionId.value && s.is_subagent
  )
})

const selectedModelHasVision = computed(() => {
  if (!selectedProviderId.value || !selectedModelName.value) return false
  const provider = providers.value.find(p => p.id === selectedProviderId.value)
  return provider?.model_vision?.[selectedModelName.value] === true
})

const taskPreview = computed(() => {
  const msg = currentTurn.value?.userMessage
  if (!msg) return '子 Agent 执行中…'
  return msg.length > 60 ? msg.slice(0, 60) + '…' : msg
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
  } else if (payload.action === 'skip_memory_search') {
    chatStore.skipMemorySearch(sessionId.value)
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
.sub-agent-bar-wrapper {
  padding: 6px 24px 8px;
  background: var(--bg-card);
}
.sub-agent-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  max-width: 768px;
  margin: 0 auto;
  padding: 5px 10px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: var(--shadow-soft);
  gap: 8px;
}
.sub-agent-bar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}
.sub-agent-btn-check {
  width: 26px;
  height: 26px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  padding: 0;
  font-family: inherit;
  flex-shrink: 0;
}
.sub-agent-btn-check:hover {
  background: var(--bg-secondary);
  color: var(--text-primary);
}
.sub-agent-btn-check.active {
  background: color-mix(in srgb, #81ae92 12%, transparent);
  color: #81ae92;
  box-shadow: 0 0 0 1px color-mix(in srgb, #81ae92 30%, transparent);
}
.sub-agent-task {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  line-height: 1.4;
}
.sub-agent-bar-right {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
.sub-agent-meta {
  font-size: 11px;
  color: var(--text-tertiary);
  font-family: monospace;
  letter-spacing: 0.3px;
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

/* ── Header 模式指示标签 ── */
.header-mode-tags {
  display: flex;
  align-items: center;
  gap: 6px;
}
.mode-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  line-height: 1;
  white-space: nowrap;
  background: color-mix(in srgb, #81ae92 10%, transparent);
  color: #81ae92;
  border: 1px solid color-mix(in srgb, #81ae92 25%, transparent);
}
.mode-tag-icon {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
}

</style>
