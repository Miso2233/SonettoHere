<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="context-backdrop"
      @click="close"
      @contextmenu.prevent="close"
      @keydown.escape="close"
    >
      <div
        class="context-menu"
        :style="{ left: position.x + 'px', top: position.y + 'px' }"
        @click.stop
        @contextmenu.stop
      >
        <button
          v-for="item in items"
          :key="item.action"
          class="context-menu-item"
          @click="select(item.action)"
        >
          <span v-if="item.icon" class="context-menu-icon">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </button>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'

export interface ContextMenuItem {
  label: string
  action: string
  icon?: string
}

export interface ContextMenuPosition {
  x: number
  y: number
}

const props = defineProps<{
  position: ContextMenuPosition
  items: ContextMenuItem[]
  visible: boolean
}>()

const emit = defineEmits<{
  select: [action: string]
  close: []
}>()

function select(action: string) {
  emit('select', action)
}

function close() {
  emit('close')
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.visible) {
    close()
  }
}

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
})
</script>

<style scoped>
.context-backdrop {
  position: fixed;
  inset: 0;
  z-index: 1000;
}

.context-menu {
  position: fixed;
  z-index: 1001;
  min-width: 120px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18);
  padding: 4px 0;
}

.context-menu-item {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 8px 16px;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  white-space: nowrap;
  transition: background 0.12s;
}

.context-menu-item:hover {
  background: color-mix(in srgb, var(--accent) 12%, transparent);
}

.context-menu-icon {
  font-size: 14px;
}
</style>
