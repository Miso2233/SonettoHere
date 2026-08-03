<template>
  <div class="studio-selector">
    <div class="dropdown">
      <button
        class="dropdown-trigger"
        :class="{ active: studioName }"
        :title="studioName || '默认工作坊（不注入工作坊配置）'"
        @click.stop="open = !open"
      >
        {{ studioName || '进入工作坊' }}
      </button>
      <div v-if="open" class="dropdown-menu">
        <button
          class="dropdown-option"
          :class="{ selected: studioName === '' }"
          @click="select('')"
        >默认</button>
        <button v-if="studios.length === 0" class="dropdown-option disabled">暂无可用的工作坊</button>
        <button
          v-for="s in studios"
          :key="s.name"
          class="dropdown-option"
          :class="{ selected: studioName === s.name }"
          :title="s.description || s.name"
          @click="select(s.name)"
        >{{ s.name }}</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { api } from '@/api'
import type { StudioInfo } from '@/types'
import { onMounted, onUnmounted, ref } from 'vue'

defineProps<{ studioName: string }>()
const emit = defineEmits<{ change: [name: string] }>()

const studios = ref<StudioInfo[]>([])
const open = ref(false)

/** 点击外部关闭下拉 */
function onDocumentClick() {
  open.value = false
}
onMounted(() => document.addEventListener('click', onDocumentClick))
onUnmounted(() => document.removeEventListener('click', onDocumentClick))

async function loadStudios() {
  try {
    const res = await api.listStudios()
    studios.value = res.studios
  } catch {
    // 静默失败
  }
}
onMounted(loadStudios)

function select(name: string) {
  open.value = false
  emit('change', name)
}
</script>

<style scoped>
.dropdown {
  position: relative;
  display: inline-block;
}
.dropdown-trigger {
  display: flex;
  align-items: center;
  gap: 4px;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  padding: 4px 8px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
}
.dropdown-trigger:hover {
  border-color: var(--border);
  background: var(--bg-secondary);
  color: var(--text-primary);
}
.dropdown-trigger.active {
  color: var(--accent);
  border-color: color-mix(in srgb, var(--accent) 30%, transparent);
}
.dropdown-menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  z-index: 200;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: var(--shadow-lg);
  min-width: 200px;
  max-height: 240px;
  overflow-y: auto;
  padding: 4px;
}
.dropdown-option {
  display: block;
  width: 100%;
  text-align: left;
  padding: 6px 10px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-primary);
  font-size: 12px;
  cursor: pointer;
  font-family: inherit;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: background 0.1s;
}
.dropdown-option:hover {
  background: var(--bg-secondary);
}
.dropdown-option.selected {
  color: var(--accent);
  font-weight: 600;
  background: color-mix(in srgb, var(--accent) 6%, transparent);
}
.dropdown-option.disabled {
  color: var(--text-secondary);
  font-style: italic;
  cursor: default;
}
</style>
