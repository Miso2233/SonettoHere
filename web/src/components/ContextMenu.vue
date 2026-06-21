<template>
  <Teleport to="body">
    <div
      v-show="visible"
      class="context-backdrop"
      @click="close"
      @contextmenu.prevent="close"
    >
      <Transition name="menu-pop">
        <div
          v-if="visible"
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
            <Icon v-if="item.icon" :name="item.icon" :size="14" />
            <span>{{ item.label }}</span>
          </button>
        </div>
      </Transition>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import Icon from '@/components/Icon.vue'
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
  background: color-mix(in srgb, var(--bg-card) 70%, transparent);
  backdrop-filter: blur(12px) saturate(1.2);
  -webkit-backdrop-filter: blur(16px) saturate(1.2);
  border: 1px solid color-mix(in srgb, var(--border) 60%, transparent);
  border-radius: 8px;
  overflow: hidden;
  box-shadow: var(--shadow-lg);
  padding: 4px 0;
  transform-origin: top left;
}

.context-menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
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

/* 弹出动画 */
.menu-pop-enter-active {
  transition: opacity 0.06s ease-out, transform 0.06s ease-out;
}
.menu-pop-leave-active {
  transition: opacity 0.08s ease-in, transform 0.08s ease-in;
}
.menu-pop-enter-from {
  opacity: 0;
  transform: scale(0.92);
}
.menu-pop-leave-to {
  opacity: 0;
  transform: scale(0.92);
}
</style>
