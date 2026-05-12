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
      >
        <div class="session-item-main">
          <span class="session-id">{{ formatId(s.session_id) }}</span>
          <span class="session-count">{{ s.message_count }} 条消息</span>
        </div>
        <button
          class="btn-delete"
          @click.stop="$emit('delete', s.session_id)"
          title="删除会话"
        >
          &times;
        </button>
      </button>
      <div v-if="sessions.length === 0" class="no-sessions">
        暂无会话
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SessionInfo } from '@/types'

defineProps<{
  sessions: SessionInfo[]
  activeId: string
}>()

defineEmits<{
  create: []
  switch: [id: string]
  delete: [id: string]
}>()

function formatId(id: string): string {
  return id.length > 10 ? id.slice(0, 10) + '…' : id
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
  gap: 2px;
  max-height: 400px;
  overflow-y: auto;
}
.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
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
  color: #c97a7a;
}
.no-sessions {
  font-size: 12px;
  color: var(--text-secondary);
  padding: 8px;
}
</style>
