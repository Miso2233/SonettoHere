<template>
  <div v-if="usage" class="context-usage" :class="level">
    <svg class="ring" viewBox="0 0 32 32">
      <circle
        class="ring-bg"
        cx="16" cy="16" r="13"
        fill="none"
        stroke-width="3"
      />
      <circle
        class="ring-fill"
        cx="16" cy="16" r="13"
        fill="none"
        stroke-width="3"
        stroke-linecap="round"
        :stroke-dasharray="circumference"
        :stroke-dashoffset="dashOffset"
      />
    </svg>
    <span class="label">{{ Math.round(usage.usage_percent) }}%</span>
    <span class="model-name">{{ usage.model_name }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ContextUsage } from '@/types'

const props = defineProps<{ usage: ContextUsage | null }>()

const circumference = 2 * Math.PI * 13

const dashOffset = computed(() => {
  if (!props.usage) return circumference
  const pct = Math.min(props.usage.usage_percent, 100)
  return circumference * (1 - pct / 100)
})

const level = computed(() => {
  if (!props.usage) return ''
  if (props.usage.usage_percent < 60) return 'safe'
  if (props.usage.usage_percent < 85) return 'warn'
  return 'danger'
})
</script>

<style scoped>
.context-usage {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}
.ring {
  width: 15px;
  height: 15px;
  flex-shrink: 0;
  margin-top: 1px;
  transform: rotate(-90deg);
}
.ring-bg {
  stroke: var(--border);
}
.ring-fill {
  transition: stroke-dashoffset 0.5s ease, stroke 0.5s ease;
}
.safe .ring-fill {
  stroke: #7ab87a;
}
.safe .label {
  color: #7ab87a;
}
.warn .ring-fill {
  stroke: #c9b44a;
}
.warn .label {
  color: #c9b44a;
}
.danger .ring-fill {
  stroke: #c97a7a;
}
.danger .label {
  color: #c97a7a;
}
.model-name {
  color: var(--text-secondary);
  opacity: 1;
}
</style>
