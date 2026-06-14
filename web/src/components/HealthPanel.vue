<template>
  <div class="health-panel" v-if="health">
    <div class="health-title">系统状态</div>
    <div class="health-items">
      <div
        v-for="item in items"
        :key="item.name"
        class="health-item"
        :title="item.tooltip"
      >
        <span class="dot" :class="item.statusClass"></span>
        <span class="label">{{ item.label }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ComponentHealth, HealthResponse } from '@/types';
import { computed } from 'vue';

const props = defineProps<{ health: HealthResponse }>()

interface HealthItem {
  name: string
  label: string
  statusClass: string
  tooltip: string
}

const items = computed<HealthItem[]>(() => {
  const h = props.health
  return [
    makeItem('LLM', h.llm),
    makeItem('MEMORY', h.memory),
    makeItem('TOOLS', h.native_tools),
    makeItem('MCP', h.mcp_tools),
  ]
})

function makeItem(label: string, c: ComponentHealth): HealthItem {
  const ok = c.status === 'ok'
  const parts: string[] = []
  if (c.latency_ms != null) parts.push(`${c.latency_ms.toFixed(0)}ms`)
  if (c.detail != null) parts.push(c.detail)
  return {
    name: label,
    label,
    statusClass: ok ? 'ok' : 'error',
    tooltip: `${label}: ${ok ? '正常' : '异常'}${parts.length ? ' — ' + parts.join(' | ') : ''}`,
  }
}
</script>

<style scoped>
.health-panel {
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.health-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.health-items {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.health-item {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: help;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot.ok {
  background: var(--status-ok);
}

.dot.error {
  background: var(--status-error);
}

.label {
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
