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
        <span class="ac-item-icon"><Icon name="sparkles" :size="14" /></span>
        <span class="ac-item-name">{{ s.name }}</span>
        <span class="ac-item-desc">{{ s.description }}</span>
      </div>
      <div v-if="!items.length" class="ac-empty">无匹配技能</div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import Icon from '@/components/Icon.vue'
import type { SkillInfo } from '@/types'
import { computed, nextTick, ref, watch } from 'vue'

const props = defineProps<{
  items: SkillInfo[]
  visible: boolean
  position: { x: number; y: number }
  activeIndex: number
}>()

const emit = defineEmits<{
  select: [skill: SkillInfo]
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

const panelStyle = computed(() => ({
  left: props.position.x + 'px',
  // 面板底边固定在光标行顶部（y 是行底，减 24 ≈ 行高），向上展开
  bottom: `${window.innerHeight - props.position.y + 28}px`,
}))

// 调试
console.log(`[SkillAutocomplete] render: visible=${props.visible}, items=${props.items.length}, activeIndex=${props.activeIndex}`)
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
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.12);
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
