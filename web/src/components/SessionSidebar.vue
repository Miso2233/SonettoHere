<template>
  <div class="session-sidebar">
    <div class="sidebar-section-header">
      <span>会话列表</span>
      <button class="btn-new" @click="$emit('create')" title="新会话">+</button>
    </div>
    <div class="session-list">
      <button
        v-for="s in sessions"
        :key="s.session_id"
        class="session-item"
        :class="{ active: s.session_id === activeId }"
        @click="$emit('switch', s.session_id)"
        @mouseenter="onSessionMouseEnter($event, s)"
        @mouseleave="onSessionMouseLeave"
      >
        <div class="session-item-main">
          <span class="session-id">{{ formatId(s.session_id) }}</span>
          <span class="session-count">{{ s.message_count }} 条消息</span>
        </div>
        <div class="session-item-right">
          <span
            v-if="(sessionStatuses ?? {})[s.session_id]?.isAwaitingUser"
            class="status-dot awaiting-user"
            title="等待用户输入"
          />
          <span
            v-else-if="(sessionStatuses ?? {})[s.session_id]?.isStreaming"
            class="status-dot streaming"
            title="Agent 运行中"
          />
          <span
            v-else-if="(sessionStatuses ?? {})[s.session_id]?.connected"
            class="status-dot connected"
            title="已连接"
          />
          <button
            class="btn-delete"
            @click.stop="$emit('delete', s.session_id)"
            title="删除会话"
          >
            &times;
          </button>
        </div>
      </button>
      <div v-if="sessions.length === 0" class="no-sessions">
        暂无会话
      </div>
    </div>

    <Transition name="card">
      <div v-if="hoveredSession" :key="hoveredSession.session_id" ref="hoverCardRef" class="session-hover-card" :style="cardStyle">
        <div class="card-row">
          <span class="card-label">ID</span>
          <span class="card-value">{{ hoveredSession.session_id }}</span>
        </div>
        <div class="card-row">
          <span class="card-label">消息</span>
          <span class="card-value">{{ hoveredSession.message_count }}</span>
        </div>
        <div class="card-divider"></div>
        <div class="card-row">
          <span class="card-label">创建时间</span>
          <span class="card-value">{{ formatRelativeTime(hoveredSession.created_at) }}</span>
        </div>
        <div class="card-row" v-if="hoveredSession.last_active">
          <span class="card-label">最近活跃</span>
          <span class="card-value">{{ formatRelativeTime(hoveredSession.last_active) }}</span>
        </div>
        <div class="card-divider" v-if="hoveredSession.last_active"></div>
        <div class="card-row">
          <span class="card-label">Agent</span>
          <span class="card-value">{{ getAgentStatus(hoveredSession.session_id) }}</span>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import type { SessionInfo } from '@/types'

const props = defineProps<{
  sessions: SessionInfo[]
  activeId: string
  sessionStatuses?: Record<string, { connected: boolean; isStreaming: boolean; isAwaitingUser: boolean }>
}>()

defineEmits<{
  create: []
  switch: [id: string]
  delete: [id: string]
}>()

const hoveredSession = ref<SessionInfo | null>(null)
const hoverCardRef = ref<HTMLElement | null>(null)
const cardTop = ref(0)
const cardLeft = ref(0)

let hoverLeaveTimer: ReturnType<typeof setTimeout> | null = null

function formatId(id: string): string {
  return id.length > 10 ? id.slice(0, 10) + '…' : id
}

function formatRelativeTime(ts: number): string {
  const diff = Date.now() - ts * 1000
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 7) return `${days}天前`
  return new Date(ts * 1000).toLocaleDateString()
}

function getAgentStatus(sessionId: string): string {
  const status = props.sessionStatuses?.[sessionId]
  if (!status?.connected) return '就绪'
  if (status.isAwaitingUser) return '需处理'
  if (status.isStreaming) return '工作中'
  return '就绪'
}

function onSessionMouseEnter(event: MouseEvent, session: SessionInfo) {
  if (hoverLeaveTimer !== null) {
    clearTimeout(hoverLeaveTimer)
    hoverLeaveTimer = null
  }
  const button = event.currentTarget as HTMLElement
  const rect = button.getBoundingClientRect()
  cardTop.value = rect.top
  cardLeft.value = rect.right + 8
  hoveredSession.value = session
  nextTick(() => adjustCardPosition(rect))
}

function onSessionMouseLeave() {
  if (hoverLeaveTimer !== null) clearTimeout(hoverLeaveTimer)
  hoverLeaveTimer = setTimeout(() => {
    hoveredSession.value = null
  }, 150)
}

function adjustCardPosition(buttonRect: DOMRect) {
  const cardEl = hoverCardRef.value
  if (!cardEl || !hoveredSession.value) return
  const cardWidth = cardEl.offsetWidth
  const cardHeight = cardEl.offsetHeight
  const vw = window.innerWidth
  const vh = window.innerHeight
  const margin = 8

  if (cardLeft.value + cardWidth > vw - margin) {
    const leftPos = buttonRect.left - cardWidth - margin
    cardLeft.value = leftPos >= margin ? leftPos : Math.max(margin, vw - cardWidth - margin)
  }
  if (cardTop.value + cardHeight > vh - margin) {
    cardTop.value = Math.max(margin, vh - cardHeight - margin)
  }
}

const cardStyle = computed(() => {
  if (!hoveredSession.value) return {}
  return {
    position: 'fixed' as const,
    top: `${cardTop.value}px`,
    left: `${cardLeft.value}px`,
    zIndex: 100,
    pointerEvents: 'none' as const,
  }
})
</script>

<style scoped>
.session-sidebar {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sidebar-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.btn-new {
  width: 24px;
  height: 24px;
  border: none;
  border-radius: 6px;
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}
.btn-new:hover {
  background: var(--accent);
  color: #fff;
}
.session-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 400px;
  overflow-y: auto;
}
.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  transition: background 0.15s;
}
.session-item:hover {
  background: var(--bg-card);
}
.session-item.active {
  background: var(--bg-card);
  box-shadow: var(--shadow);
}
.session-item-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.session-id {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}
.session-count {
  font-size: 11px;
  color: var(--text-secondary);
}
.btn-delete {
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 16px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s;
}
.session-item:hover .btn-delete {
  opacity: 1;
}
.btn-delete:hover {
  color: #ef4444;
}
.no-sessions {
  font-size: 12px;
  color: var(--text-secondary);
  padding: 8px;
}

.session-item-right {
  display: flex;
  align-items: center;
  gap: 4px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot.connected {
  background: #22c55e;
}

.status-dot.streaming {
  background: #22c55e;
  animation: pulse 1.2s ease-in-out infinite;
}

.status-dot.awaiting-user {
  background: #f59e0b;
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.3); }
}

/* ── Hover card ── */
.session-hover-card {
  min-width: 220px;
  padding: 8px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  font-size: 12px;
  line-height: 1.6;
  white-space: nowrap;
}
.card-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}
.card-label {
  color: var(--text-secondary);
}
.card-value {
  font-variant-numeric: tabular-nums;
  color: var(--text-primary);
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.card-divider {
  height: 1px;
  background: var(--border);
  margin: 4px 0;
}

.card-enter-active,
.card-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.card-enter-from,
.card-leave-to {
  opacity: 0;
  transform: translateX(-8px);
}
</style>
