<template>
  <span class="ref-chip" :class="'ref-chip--' + type" :title="tooltip">
    <span class="ref-chip-icon">
      <Icon :name="iconName" :size="12" />
    </span>
    <span class="ref-chip-label">{{ label }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import Icon from '@/components/Icon.vue'

const props = defineProps<{
  type: 'file' | 'cite'
  label: string
  path?: string
  text?: string
}>()

const iconName = computed(() => (props.type === 'file' ? 'file' : 'cite-speech'))

const tooltip = computed(() => {
  if (props.type === 'file' && props.path) return props.path
  if (props.type === 'cite' && props.text) return props.text
  return props.label
})
</script>

<style scoped>
.ref-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  background: color-mix(in srgb, var(--text-primary) 8%, transparent);
  border-radius: 5px;
  font-size: 11px;
  color: var(--text-secondary);
  max-width: 200px;
  overflow: hidden;
  user-select: none;
  white-space: nowrap;
}
.ref-chip-icon {
  display: inline-flex;
  flex-shrink: 0;
  opacity: 0.7;
}
.ref-chip-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
