<template>
  <div class="app-layout">
    <aside class="sidebar" :class="{ collapsed: effectiveCollapsed }" @click="onSidebarClick">
      <div class="sidebar-header">
        <h1 class="logo">SonettoHere</h1>
      </div>
      <div class="sidebar-icon-collapsed">
        <svg viewBox="0 0 64 64" fill="currentColor" style="width:22px;height:22px"><path d="M21.956,48.12,21.18,52H20a1,1,0,0,0-1,1v3a1,1,0,0,0,0,2v3a1,1,0,0,0,1,1H44a1,1,0,0,0,1-1V58a1,1,0,0,0,0-2V53a1,1,0,0,0-1-1H42.82l-.776-3.88A19.007,19.007,0,0,0,50.064,26.1a1,1,0,1,0-1.9.621,17.027,17.027,0,0,1-7.829,20.1.973.973,0,0,0-.208.18H33V43.916A6.95,6.95,0,0,0,39,37V32.708A1,1,0,0,0,37.293,32l-2.648,2.648a.378.378,0,0,1-.605-.1.382.382,0,0,1-.04-.169V28.708a1,1,0,0,0-1.581-.813L28.1,30.981A7.412,7.412,0,0,0,25,37a7.006,7.006,0,0,0,.4,2.339,1,1,0,0,0,1.885-.668A5,5,0,0,1,27,37a5.41,5.41,0,0,1,2.26-4.392L32,30.651v3.732a2.378,2.378,0,0,0,4.059,1.681L37,35.123V37a4.961,4.961,0,0,1-4,4.891V39a1,1,0,0,0-2,0v2.891a4.932,4.932,0,0,1-1.235-.418,4.992,4.992,0,0,1-.824-.518,1,1,0,0,0-1.224,1.582A6.851,6.851,0,0,0,31,43.916V47H23.873a.973.973,0,0,0-.208-.18A17,17,0,0,1,22.36,18H41.63a17.016,17.016,0,0,1,4.2,4.114,1,1,0,0,0,1.627-1.164A19,19,0,0,0,43,16.527V12a1,1,0,0,0-.445-.832l-3-2A1.006,1.006,0,0,0,39,9H37V7A5,5,0,0,0,27,7V9H25a1.006,1.006,0,0,0-.555.168l-3,2A1,1,0,0,0,21,12v4.517a18.984,18.984,0,0,0,.956,31.6ZM40.181,49l.6,3H31a1,1,0,0,0,0,2H43v2H31a1,1,0,0,0,0,2H43v2H21V58h2a1,1,0,0,0,0-2H21V54h5a1,1,0,0,0,0-2H23.22l.6-3ZM29,7a3,3,0,0,1,6,0V9H29Zm-6,5.535L25.3,11H38.7L41,12.535V16H23Z"/></svg>
      </div>
      <nav class="sidebar-nav">
        <router-link to="/" class="nav-item">
          <Icon name="chat" :size="18" /> <span class="nav-label">对话&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;CHATTING</span>
        </router-link>
        <router-link to="/memory" class="nav-item">
          <Icon name="memory" :size="18" /> <span class="nav-label">记忆&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;MEMORY</span>
        </router-link>
        <router-link to="/playground" class="nav-item pg-nav">动态 NEWS</router-link>
        <div class="settings-area" ref="settingsTriggerRef">
          <button class="nav-item settings-btn" :class="{ active: showSettingsMenu }" @click="toggleSettingsMenu">
            <Icon name="settings" :size="18" /> <span class="nav-label">设置&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;SETTINGS</span>
          </button>
        </div>
      </nav>
      <Transition name="popup">
        <div v-if="showSettingsMenu" ref="settingsPopupRef" class="settings-popup" :style="{ top: popupTop, left: popupLeft }" @click.stop>
          <div class="popup-header">设置</div>
          <router-link to="/providers" class="popup-item" @click="closeSettingsMenu">模型 MODELS</router-link>
          <router-link to="/soul" class="popup-item" @click="closeSettingsMenu">人设 SOUL</router-link>
          <router-link to="/user" class="popup-item" @click="closeSettingsMenu">用户 USER</router-link>
          <router-link to="/path-whitelist" class="popup-item" @click="closeSettingsMenu">路径白名单</router-link>
          <router-link to="/sonetto-blocker" class="popup-item" @click="closeSettingsMenu">拒止锚</router-link>
          <div class="popup-divider"></div>
          <button class="popup-item popup-action" :class="{ restarting }" :disabled="restarting" @click="handleRestart">
            {{ restarting ? '重启中...' : '重启服务' }}
          </button>
        </div>
      </Transition>
      <SessionSidebar
        :sessions="sessions"
        :active-id="sessionId"
        :session-statuses="allSessionStatuses"
        :collapsed="effectiveCollapsed"
        @create="createSession"
        @switch="handleSwitchSession"
        @delete="deleteSession"
        @constify="handleConstify"
        @unconstify="handleUnconstify"
      />
      <HealthPanel :health="health!" v-if="health" />
    </aside>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import HealthPanel from '@/components/HealthPanel.vue';
import Icon from '@/components/Icon.vue';
import SessionSidebar from '@/components/SessionSidebar.vue';
import { allSessionStatuses } from '@/composables/useChat';
import { health, startPolling, useHealth } from '@/composables/useHealth';
import { constifySession, unconstifySession, useSession } from '@/composables/useSession';
import { useSidebar } from '@/composables/useSidebar';
import { api } from '@/api';
import { ref, onMounted, onUnmounted, nextTick } from 'vue';
import { useRouter } from 'vue-router';

const { effectiveCollapsed, toggleSidebar } = useSidebar()

const showSettingsMenu = ref(false)
const settingsTriggerRef = ref<HTMLElement | null>(null)
const settingsPopupRef = ref<HTMLElement | null>(null)
const popupTop = ref('0px')
const popupLeft = ref('228px')
const restarting = ref(false)

async function handleRestart() {
  if (restarting.value) return
  if (!window.confirm('确定要重启 SonettoHere 服务吗？正在进行的对话可能会中断。')) return
  restarting.value = true
  closeSettingsMenu()
  api.restart()
  const poll = async () => {
    for (let i = 0; i < 60; i++) {
      await new Promise(r => setTimeout(r, 2000))
      try {
        await api.health()
        location.reload(); return
      } catch { /* still down */ }
    }
    restarting.value = false
  }
  poll()
}

function toggleSettingsMenu() {
  showSettingsMenu.value = !showSettingsMenu.value
  nextTick(() => updatePopupPosition())
}

function closeSettingsMenu() {
  showSettingsMenu.value = false
}

function updatePopupPosition() {
  if (settingsTriggerRef.value) {
    const rect = settingsTriggerRef.value.getBoundingClientRect()
    popupTop.value = `${rect.top}px`
    popupLeft.value = `${rect.right + 8}px`
  }
}

function onDocumentClick(e: MouseEvent) {
  if (!showSettingsMenu.value) return
  const trigger = settingsTriggerRef.value
  const popup = settingsPopupRef.value
  if (trigger && popup &&
      !trigger.contains(e.target as Node) &&
      !popup.contains(e.target as Node)) {
    closeSettingsMenu()
  }
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
})

onUnmounted(() => {
  document.removeEventListener('click', onDocumentClick)
})

function onSidebarClick(e: MouseEvent) {
  if (e.target === e.currentTarget) {
    toggleSidebar()
  }
}

const router = useRouter()

function handleSwitchSession(id: string) {
  switchSession(id)
  router.push('/')
}

function handleConstify(id: string, name: string) {
  if (name && name.trim()) {
    constifySession(id, name.trim())
  }
}

function handleUnconstify(id: string) {
  if (window.confirm('确定取消固定此会话？')) {
    unconstifySession(id)
  }
}

const { sessionId, sessions, createSession, switchSession, deleteSession } =
  useSession()

useHealth()

onMounted(() => {
  startPolling()
})
</script>

<style>
*,
*::before,
*::after {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

:root {
  --bg-primary: #ffffff;
  --bg-secondary: #f9fafb;
  --bg-card: #ffffff;
  --text-primary: #1f2937;
  --text-secondary: #6b7280;
  --text-tertiary: #9ca3af;
  --accent: #000000;
  --accent-light: #b9b9b9;
  --border: #e5e7eb;
  --user-bubble: #ffffff;
  --status-ok: #000000;
  --status-error: #ef4444;
  --status-warn: #f59e0b;
  --shadow: 0 2px 8px rgba(0, 0, 0, 0.08);       /* 兼容别名，同级 --shadow-md */
  --shadow-xs: 0 1px 3px rgba(0, 0, 0, 0.04);   /* 极浅分割 */
  --shadow-soft: 0 8px 24px rgba(0, 0, 0, 0.06); /* 大面积超浅阴影（输入框） */
  --shadow-sm: 0 1px 4px rgba(0, 0, 0, 0.06);   /* 卡片、条目 hover */
  --shadow-md: 0 2px 8px rgba(0, 0, 0, 0.08);   /* 气泡、通用卡片 */
  --shadow-lg: 0 4px 16px rgba(0, 0, 0, 0.12);  /* 下拉菜单、浮层 */
  --shadow-xl: 0 6px 28px rgba(0, 0, 0, 0.18);  /* 模态弹窗、重型浮层 */
  --radius: 10px;
}

::selection {
  background: color-mix(in srgb, var(--accent) 10%, transparent);
  color: #000000;
}

/* ── Scrollbar ── */
* {
  scrollbar-width: thin;
  scrollbar-color: var(--border) transparent;
}
*::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
*::-webkit-scrollbar-track {
  background: transparent;
}
*::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 3px;
}
*::-webkit-scrollbar-thumb:hover {
  background: var(--text-secondary);
}

html, body {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  font-size: 15px;
  color: var(--text-primary);
  background: var(--bg-primary);
}

#app {
  height: 100%;
}

.app-layout {
  display: flex;
  height: 100%;
}

.sidebar {
  width: 220px;
  min-width: 220px;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 24px 20px;
  gap: 24px;
  position: relative;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  justify-content: center;
  transition: max-height 0.25s ease, opacity 0.2s ease 0.05s, transform 0.25s ease 0.05s, padding 0.25s ease, margin 0.25s ease;
  overflow: hidden;
  max-height: 100px;
}

.logo {
  font-size: 18px;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: -0.3px;
}

.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: var(--radius);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  transition: background 0.15s, color 0.15s;
}

.nav-item:hover {
  background: var(--bg-card);
  color: var(--text-primary);
}

.nav-item.router-link-active {
  background: var(--bg-card);
  color: var(--accent);
  font-weight: 600;
}

.nav-label {
  transition: max-width 0.25s ease, opacity 0.2s ease 0.05s, transform 0.25s ease 0.05s, padding 0.25s ease, margin 0.25s ease;
  overflow: hidden;
  white-space: nowrap;
  max-width: 200px;
}

.pg-nav {
  margin-top: 16px;
  border-top: 1px solid var(--border);
  padding-top: 12px;
  border-radius: 0;
  font-size: 12px;
  color: var(--text-secondary);
  opacity: 0.7;
}

.pg-nav:hover {
  opacity: 1;
}

/* ── Settings trigger ── */
.settings-area {
  margin-top: auto;
}

.settings-btn {
  width: 100%;
  border: none;
  cursor: pointer;
  font-family: inherit;
  font-size: 14px;
  background: transparent;
}

.settings-btn.active {
  background: var(--bg-card);
  color: var(--accent);
  font-weight: 600;
}

.settings-btn:hover {
  background: var(--bg-card);
  color: var(--text-primary);
}

/* ── Settings popup ── */
.settings-popup {
  position: fixed;
  z-index: 200;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-lg);
  min-width: 170px;
  padding: 6px;
  overflow: hidden;
}

.popup-header {
  padding: 8px 12px 6px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.popup-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 6px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  transition: background 0.15s, color 0.15s;
}

.popup-item:hover {
  background: var(--bg-secondary);
  color: var(--text-primary);
}

.popup-item.router-link-active {
  color: var(--accent);
  font-weight: 600;
  background: var(--bg-secondary);
}

.popup-divider {
  height: 1px;
  background: var(--border);
  margin: 4px 0;
}

.popup-action {
  width: 100%;
  border: none;
  cursor: pointer;
  font-family: inherit;
  font-size: 14px;
  background: transparent;
  color: #dc2626;
}
.popup-action:hover:not(:disabled) {
  background: var(--bg-secondary);
  color: #b91c1c;
}
.popup-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.popup-action.restarting {
  color: #f59e0b;
}

/* ── Popup transition ── */
.popup-enter-active {
  transition: opacity 0.12s ease, transform 0.12s ease;
}
.popup-leave-active {
  transition: opacity 0.08s ease, transform 0.08s ease;
}
.popup-enter-from,
.popup-leave-to {
  opacity: 0;
  transform: translateX(-6px);
}

.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.sidebar .health-panel {
  transition: max-height 0.25s ease, opacity 0.2s ease 0.05s, padding 0.25s ease, margin 0.25s ease;
  overflow: hidden;
  max-height: 300px;
}

/* ── Collapsible sidebar ── */
.sidebar {
  position: relative;
  transition: width 0.25s ease, min-width 0.25s ease, padding 0.25s ease;
}
.sidebar.collapsed {
  width: 58px;
  min-width: 58px;
  padding: 24px 10px;
  align-items: center;
  overflow: hidden;
}
.sidebar-icon-collapsed {
  display: none;
  justify-content: center;
}
.sidebar.collapsed .sidebar-header {
  max-height: 0;
  opacity: 0;
  transform: translateX(-30px);
  overflow: hidden;
  padding: 0;
  margin: 0;
}
.sidebar.collapsed .sidebar-icon-collapsed {
  display: flex;
  position: absolute;
  top: 22px;
  left: 50%;
  transform: translateX(-50%);
}
.sidebar.collapsed .sidebar-nav {
  width: 100%;
  align-items: center;
  padding-top: 10px;
}
.sidebar.collapsed .nav-item {
  justify-content: center;
  padding: 8px;
  gap: 0;
  width: 100%;
  overflow: hidden;
}
.sidebar.collapsed .nav-label {
  max-width: 0;
  opacity: 0;
  transform: translateX(-24px);
  overflow: hidden;
  white-space: nowrap;
  padding: 0;
  margin: 0;
}
.sidebar.collapsed .pg-nav {
  display: none;
}
.sidebar.collapsed .health-panel {
  max-height: 0;
  opacity: 0;
  overflow: hidden;
  padding: 0;
  margin: 0;
}

/* ── Sidebar background image with blur + white overlay ── */
.sidebar::before {
  content: '';
  position: absolute;
  inset: -5%;
  background-image: url('/images/sidebar-bg.jpg');
  background-size: cover;
  background-position: left center;
  background-repeat: no-repeat;
  filter: blur(10px);
  transform: scale(1.05);
  z-index: 0;
  pointer-events: none;
}

.sidebar::after {
  content: '';
  position: absolute;
  inset: 0;
  background: #ffffffd3;
  z-index: 0;
  pointer-events: none;
}

.sidebar > :not(.settings-popup) {
  position: relative;
  z-index: 1;
}

/* ── Shared markdown rendered content ── */
.markdown-body {
  font-size: 16px;
  line-height: 1.6;
  color: var(--text-primary);
  word-break: break-word;
}

.markdown-body h1,
.markdown-body h2,
.markdown-body h3,
.markdown-body h4,
.markdown-body h5,
.markdown-body h6 {
  margin: 16px 0 8px;
  font-weight: 600;
  line-height: 1.3;
}
.markdown-body h1 { font-size: 1.5em; }
.markdown-body h2 { font-size: 1.3em; }
.markdown-body h3 { font-size: 1.15em; }
.markdown-body h4 { font-size: 1em; }
.markdown-body h5 { font-size: 0.9em; }
.markdown-body h6 { font-size: 0.85em; color: var(--text-secondary); }

.markdown-body > *:first-child { margin-top: 0; }
.markdown-body > *:last-child  { margin-bottom: 0; }

.markdown-body p {
  margin: 8px 0;
}

.markdown-body ul,
.markdown-body ol {
  padding-left: 20px;
  margin: 8px 0;
}

.markdown-body li {
  margin: 4px 0;
}

.markdown-body code {
  background: var(--bg-primary);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 0.9em;
  font-family: 'SF Mono', 'Consolas', monospace;
}

.markdown-body pre {
  background: var(--bg-primary);
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
}

.markdown-body pre code {
  background: none;
  padding: 0;
  border-radius: 0;
  font-size: 13px;
}

.markdown-body blockquote {
  border-left: 3px solid var(--accent);
  padding: 4px 12px;
  margin: 8px 0;
  color: var(--text-secondary);
}

.markdown-body table {
  border-collapse: collapse;
  margin: 8px 0;
  width: 100%;
}

.markdown-body th,
.markdown-body td {
  border: 1px solid var(--border);
  padding: 6px 12px;
  text-align: left;
}

.markdown-body th {
  background: var(--bg-secondary);
  font-weight: 600;
}

.markdown-body a {
  color: var(--accent);
  text-decoration: underline;
}
.markdown-body a:hover {
  opacity: 0.8;
}

.markdown-body strong {
  font-weight: 600;
}

.markdown-body hr {
  border: none;
  border-top: 1px solid var(--border);
  margin: 16px 0;
}

.markdown-body img {
  max-width: 100%;
  border-radius: 8px;
}

.markdown-body input[type="checkbox"] {
  margin-right: 6px;
  accent-color: var(--accent);
}
</style>
