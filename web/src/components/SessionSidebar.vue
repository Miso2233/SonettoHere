<template>
  <div class="session-sidebar" :class="{ collapsed }">
    <div class="sidebar-section-header">
      <span>会话列表</span>
      <button class="btn-new" @click="$emit('create')" title="新会话">+</button>
    </div>
    <div class="session-list">

      <!-- ── 已保存（固定会话）── -->
      <div v-if="constSessions.length > 0" class="const-section">
        <div class="section-label">已保存</div>
        <div
          v-for="(s, ci) in constSessions"
          :key="s.session_id"
          class="session-item is-const"
          :class="{ active: s.session_id === activeId }"
          @click="$emit('switch', s.session_id)"
          @contextmenu.prevent="onSessionContextMenu($event, s)"
          @mouseenter="onSessionMouseEnter($event, s)"
          @mouseleave="onSessionMouseLeave"
        >
          <div class="session-item-main">
            <span class="session-id">
              <Icon name="pin" :size="12" style="margin-right: 3px; flex-shrink: 0;" />
              <span class="const-name-text">{{ s.const_name || '未命名' }}</span>
              <span v-if="s.is_subagent" class="sub-badge" title="子 Agent 会话（只读）">sub</span>
            </span>
            <span class="session-count">{{ formatRelativeTime(s.last_active ?? s.created_at) }} · {{ s.message_count }} 条消息</span>
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
        </div>
      </div>

      <!-- ── 临时会话 ── -->
      <div class="temp-section">
        <div v-if="constSessions.length > 0" class="section-label">临时会话</div>
        <div
          v-for="(s, index) in tempSessions"
          :key="s.session_id"
          class="session-item"
          :class="{ active: s.session_id === activeId }"
          @click="$emit('switch', s.session_id)"
          @contextmenu.prevent="onSessionContextMenu($event, s)"
          @mouseenter="onSessionMouseEnter($event, s)"
          @mouseleave="onSessionMouseLeave"
        >
          <div class="session-item-main">
            <span class="session-id">
              Session #{{ getSessionDisplayIndex(s) }}
              <span v-if="s.is_subagent" class="sub-badge" title="子 Agent 会话（只读）">sub</span>
            </span>
            <span class="session-count">{{ formatRelativeTime(s.last_active ?? s.created_at) }} · {{ s.message_count }} 条消息</span>
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
        </div>
      </div>

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

    <!-- ── 右键菜单 ── -->
    <ContextMenu
      :position="ctxMenuPos"
      :items="ctxMenuItems"
      :visible="ctxMenuVisible"
      @select="handleContextMenuSelect"
      @close="closeContextMenu"
    />
  </div>
</template>

<script setup lang="ts">
import type { SessionInfo } from '@/types';
import ContextMenu from '@/components/ContextMenu.vue';
import Icon from '@/components/Icon.vue';
import { computed, nextTick, ref } from 'vue';

const props = defineProps<{
  sessions: SessionInfo[]
  activeId: string
  sessionStatuses?: Record<string, { connected: boolean; isStreaming: boolean; isAwaitingUser: boolean }>
  collapsed?: boolean
}>()

const emit = defineEmits<{
  create: []
  switch: [id: string]
  delete: [id: string]
  constify: [id: string]
  unconstify: [id: string]
}>()

// ── 分区计算 ──────────────────────────────────────────────────

function getSessionDisplayIndex(s: SessionInfo): number {
  return props.sessions.length - props.sessions.findIndex(x => x.session_id === s.session_id)
}

const constSessions = computed(() =>
  props.sessions.filter(s => s.is_const)
)

const tempSessions = computed(() =>
  props.sessions.filter(s => !s.is_const)
)

// ── Hover card ────────────────────────────────────────────────

const hoveredSession = ref<SessionInfo | null>(null)
const hoverCardRef = ref<HTMLElement | null>(null)
const cardTop = ref(0)
const cardLeft = ref(0)

let hoverLeaveTimer: ReturnType<typeof setTimeout> | null = null

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

// ── 右键菜单 ──────────────────────────────────────────────────

const ctxMenuVisible = ref(false)
const ctxMenuPos = ref({ x: 0, y: 0 })
const ctxMenuSession = ref<SessionInfo | null>(null)

const ctxMenuItems = computed(() => {
  const s = ctxMenuSession.value
  if (!s) return []
  if (s.is_const) {
    return [
      { label: '固定会话…', action: 'constify', icon: 'pin' },
      { label: '取消固定', action: 'unconstify' },
    ]
  }
  return [
    { label: '固定会话…', action: 'constify', icon: 'pin' },
  ]
})

function onSessionContextMenu(event: MouseEvent, session: SessionInfo) {
  // 关闭 hover card
  if (hoverLeaveTimer !== null) {
    clearTimeout(hoverLeaveTimer)
    hoverLeaveTimer = null
  }
  hoveredSession.value = null

  ctxMenuSession.value = session
  ctxMenuPos.value = { x: event.clientX, y: event.clientY }
  ctxMenuVisible.value = true
}

function handleContextMenuSelect(action: string) {
  const s = ctxMenuSession.value
  if (!s) return
  if (action === 'constify') {
    emit('constify', s.session_id)
  } else if (action === 'unconstify') {
    emit('unconstify', s.session_id)
  }
  closeContextMenu()
}

function closeContextMenu() {
  ctxMenuVisible.value = false
  ctxMenuSession.value = null
}
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
.sidebar-section-header span {
  transition: max-width 0.25s ease, opacity 0.2s ease 0.05s, transform 0.25s ease 0.05s, padding 0.25s ease, margin 0.25s ease;
  overflow: hidden;
  white-space: nowrap;
  display: inline-block;
  max-width: 200px;
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

/* ── Section label ── */
.section-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-tertiary, #9ca3af);
  text-transform: uppercase;
  letter-spacing: 0.4px;
  padding: 4px 12px 2px;
}

/* ── Session items ── */
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

/* Const 会话外观 */
.session-item.is-const {
  border-left: 2px solid var(--accent);
}

.session-item-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  transition: max-height 0.25s ease, opacity 0.2s ease 0.05s, transform 0.25s ease 0.05s, padding 0.25s ease, margin 0.25s ease;
  overflow: hidden;
  max-height: 80px;
}
.session-id {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 2px;
}
.const-name-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sub-badge {
  display: inline-block;
  margin-left: 4px;
  padding: 0 4px;
  font-size: 9px;
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 3px;
  vertical-align: middle;
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
  transition: max-width 0.25s ease, opacity 0.15s ease 0.05s, transform 0.25s ease 0.05s, color 0.15s, padding 0.25s ease, margin 0.25s ease;
  overflow: hidden;
  max-width: 22px;
}
.session-item:hover .btn-delete {
  opacity: 1;
}
.btn-delete:hover {
  color: var(--status-error);
}
.no-sessions {
  font-size: 12px;
  color: var(--text-secondary);
  padding: 8px;
  transition: max-height 0.25s ease, opacity 0.2s ease 0.05s, padding 0.25s ease, margin 0.25s ease;
  overflow: hidden;
  max-height: 40px;
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
  background: var(--status-ok);
}

.status-dot.streaming {
  background: var(--status-ok);
  animation: pulse 1.2s ease-in-out infinite;
}

.status-dot.awaiting-user {
  background: var(--status-warn);
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

/* ── Collapsed icon-only mode ── */
.session-sidebar.collapsed .sidebar-section-header {
  justify-content: center;
}
.session-sidebar.collapsed .sidebar-section-header span {
  max-width: 0;
  opacity: 0;
  transform: translateX(-24px);
  overflow: hidden;
  white-space: nowrap;
  display: inline-block;
  padding: 0;
  margin: 0;
}
.session-sidebar.collapsed .session-item {
  justify-content: center;
  padding: 6px;
}
.session-sidebar.collapsed .session-item-main {
  max-height: 0;
  max-width: 0;
  min-width: 0;
  opacity: 0;
  overflow: hidden;
  transform: translateX(-24px);
  padding: 0;
  margin: 0;
}
.session-sidebar.collapsed .btn-delete {
  max-width: 0;
  opacity: 0;
  overflow: hidden;
  transform: translateX(-24px);
  padding: 0;
  margin: 0;
  border: none;
}
.session-sidebar.collapsed .no-sessions {
  max-height: 0;
  opacity: 0;
  overflow: hidden;
  padding: 0;
  margin: 0;
}
/* collapsed 时隐藏分区 label */
.session-sidebar.collapsed .section-label {
  max-height: 0;
  opacity: 0;
  overflow: hidden;
  padding: 0;
  margin: 0;
}
/* collapsed 时隐藏 const 左侧边框 */
.session-sidebar.collapsed .session-item.is-const {
  border-left: none;
}
</style>
