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

    <div class="hover-card">
      <div class="card-row">
        <span class="card-label">Current</span>
        <span class="card-value">{{ formatTokens(usage.current_tokens) }}</span>
      </div>
      <div class="card-row">
        <span class="card-label">Max</span>
        <span class="card-value">{{ formatTokens(usage.max_tokens) }}</span>
      </div>
      <div class="card-divider"></div>
      <div class="card-row">
        <span class="card-label">Used</span>
        <span class="card-value">{{ Math.round(usage.usage_percent) }}%</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ContextUsage } from '@/types'

const props = defineProps<{ usage: ContextUsage | null }>()

const circumference = 2 * Math.PI * 13

function formatTokens(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return (n / 1_000).toFixed(1) + 'K'
  return n.toLocaleString()
}

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
.context-usage {
  position: relative;
}
.context-usage:hover .hover-card {
  visibility: visible;
  opacity: 1;
  transform: translateY(0);
}
.model-name {
  color: var(--text-secondary);
  opacity: 1;
}
.hover-card {
  visibility: hidden;
  opacity: 0;
  transform: translateY(-4px);
  transition: visibility 0.15s ease, opacity 0.15s ease, transform 0.15s ease;
  pointer-events: none;
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  z-index: 100;
  min-width: 160px;
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
}
.card-divider {
  height: 1px;
  background: var(--border);
  margin: 4px 0;
}
</style>
