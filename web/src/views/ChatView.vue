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
      <div class="chat-header-left">
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
            {{ autoApprove ? '自动' : '检查' }}
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
        <TaskTrackerBar :data="taskTrackerData as any" />
      </div>
      <button
        class="restart-btn"
        :class="{ restarting: restarting }"
        :disabled="restarting"
        @click="handleRestart"
        title="重启后端服务"
      >
        {{ restarting ? '重启中...' : '重启SonettoHere服务' }}
      </button>
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
      @send="onSend"
      @stop="cancel"
      @model-change="onModelChange"
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
const restarting = ref(false)

async function handleRestart() {
  if (restarting.value) return
  if (!window.confirm('确定要重启SonettoHere服务吗？正在进行的对话可能会中断。')) return
  restarting.value = true
  try {
    await fetch('/api/restart', { method: 'POST' })
  } catch { /* server will close connection, expected */ }
  const poll = async () => {
    for (let i = 0; i < 60; i++) {
      await new Promise(r => setTimeout(r, 2000))
      try {
        const res = await fetch('/api/health')
        if (res.ok) { location.reload(); return }
      } catch { /* still down */ }
    }
    restarting.value = false
  }
  poll()
}

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

function onSend(text: string, refs: ParsedRef[], providerId?: string, modelName?: string) {
  send(text, refs, providerId, modelName)
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
  justify-content: space-between;
  gap: 20px;
  padding: 12px 24px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-card);
}
.chat-header-left {
  display: flex;
  align-items: center;
  gap: 20px;
  min-width: 0;
  flex: 1;
}
.private-toggle,
.auto-approve-toggle {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-width: 62px;
  height: 26px;
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
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
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

.restart-btn {
  padding: 4px 10px;
  border: 1px solid #dc2626;
  border-radius: 6px;
  background: #dc2626;
  color: #000;
  font-size: 12px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s;
  flex-shrink: 0;
}
.restart-btn:hover:not(:disabled) {
  background: #b91c1c;
  border-color: #b91c1c;
  color: #000;
}
.restart-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.restart-btn.restarting {
  background: #f59e0b;
  border-color: #f59e0b;
  color: #000;
}
</style>
