<template>
  <Teleport to="body">
    <div v-if="visible" class="ac-backdrop" @click="$emit('close')" />
    <div v-if="visible" ref="panelRef" class="ac-panel" :style="panelStyle">
      <div
        v-for="(s, i) in items"
        :key="s.name"
        class="ac-item"
        :class="{ active: i === activeIndex }"
        @click="$emit('select', s)"
        @mouseenter="$emit('update:activeIndex', i)"
      >
        <span class="ac-item-icon"><Icon :name="iconName" :size="14" /></span>
        <span class="ac-item-name" v-html="highlightName(s.name)"></span>
        <span class="ac-item-desc">{{ s.description }}</span>
      </div>
      <div v-if="!items.length" class="ac-empty">无匹配</div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import Icon from '@/components/Icon.vue'
import { computed, nextTick, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  items: { name: string; description: string }[]
  visible: boolean
  position: { x: number; y: number }
  activeIndex: number
  filterText: string
  iconName?: string
}>(), {
  iconName: 'sparkles',
})

const emit = defineEmits<{
  select: [item: { name: string; description: string }]
  close: []
  'update:activeIndex': [index: number]
}>()

const panelRef = ref<HTMLElement | null>(null)

// 自动滚动：激活项超出可视区域时翻页
watch(() => props.activeIndex, async () => {
  await nextTick()
  const panel = panelRef.value
  if (!panel) return
  const active = panel.querySelector('.ac-item.active') as HTMLElement | null
  if (!active) return
  const panelRect = panel.getBoundingClientRect()
  const itemRect = active.getBoundingClientRect()
  if (itemRect.top < panelRect.top) {
    panel.scrollTop -= panelRect.top - itemRect.top
  } else if (itemRect.bottom > panelRect.bottom) {
    panel.scrollTop += itemRect.bottom - panelRect.bottom
  }
})

/** 将 name 中匹配 filterText 的部分用 <strong> 包裹 */
function highlightName(name: string): string {
  if (!props.filterText) return name
  const lower = name.toLowerCase()
  const needle = props.filterText.toLowerCase()
  if (!lower.includes(needle)) return name
  const re = new RegExp(`(${needle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
  return name.replace(re, '<strong>$1</strong>')
}

const panelStyle = computed(() => ({
  left: props.position.x + 'px',
  bottom: `${window.innerHeight - props.position.y + 28}px`,
}))
</script>

<style scoped>
.ac-backdrop {
  position: fixed;
  inset: 0;
  z-index: 999;
}
.ac-panel {
  position: fixed;
  z-index: 1000;
  min-width: 240px;
  max-width: 360px;
  max-height: 280px;
  overflow-y: auto;
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  box-shadow: var(--shadow-xl);
  padding: 4px;
}
.ac-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.1s;
}
.ac-item.active,
.ac-item:hover {
  background: #f3f4f6;
}
.ac-item-icon {
  display: inline-flex;
  flex-shrink: 0;
  color: var(--accent);
  opacity: 0.7;
}
.ac-item-name {
  font-size: 13px;
  font-weight: 600;
  color: #111827;
  white-space: nowrap;
  flex-shrink: 0;
}
.ac-item-desc {
  font-size: 11px;
  color: #6b7280;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ac-empty {
  padding: 10px 12px;
  font-size: 12px;
  color: #9ca3af;
  text-align: center;
}
</style>

<style>
/* v-html 渲染的加粗匹配字符 */
.ac-item-name strong {
  color: var(--accent, #2563eb);
  font-weight: 700;
}
</style>
