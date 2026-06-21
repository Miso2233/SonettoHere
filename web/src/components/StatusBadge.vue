<template>
  <span class="status-badge hover-trigger" :class="connected ? 'connected' : 'disconnected'">
    <span class="dot"></span>
    {{ connected ? '已连接' : '未连接' }}
    <div v-if="health" class="hover-card card-health">
      <div class="health-title">系统状态</div>
      <div
        v-for="(item, idx) in items"
        :key="item.name"
        class="health-section"
      >
        <div v-if="idx > 0" class="card-divider"></div>
        <div class="section-header">
          <span class="section-name">{{ item.name }}</span>
          <span class="section-status" :class="item.ok ? 'status-ok' : 'status-err'">
            {{ item.ok ? '正常' : '异常' }}
          </span>
        </div>
        <div class="section-detail">
          <span v-if="item.latency != null" class="detail-item">{{ item.latency }}</span>
          <span v-if="item.info" class="detail-item detail-text">{{ item.info }}</span>
        </div>
      </div>
      <div class="card-divider"></div>
      <div class="card-row">
        <span class="card-label">{{ health.version }}</span>
        <span class="card-value" :class="health.status === 'ok' ? 'status-ok' : 'status-err'">
          {{ health.status === 'ok' ? '就绪' : '部分异常' }}
        </span>
      </div>
    </div>
  </span>
</template>

<script setup lang="ts">
import type { ComponentHealth, HealthResponse } from '@/types';
import { computed } from 'vue';

const props = defineProps<{
  connected: boolean
  health: HealthResponse | null
}>()

const items = computed(() => {
  if (!props.health) return []
  const result = [
    makeItem('LLM', props.health.llm),
    makeItem('MEMORY', props.health.memory),
    makeItem('TOOLS', props.health.native_tools),
    makeItem('MCP', props.health.mcp_tools),
  ]
  if (props.health.anthropic_skills_count != null) {
    result.push({
      name: 'ANTHROPIC_SKILLS',
      ok: true,
      latency: '0 ms',
      info: `${props.health.anthropic_skills_count} 个技能`,
    })
  }
  return result
})

function makeItem(name: string, c: ComponentHealth) {
  const parts: string[] = []
  if (c.detail) parts.push(c.detail)
  return {
    name,
    ok: c.status === 'ok',
    latency: c.latency_ms != null ? `${c.latency_ms.toFixed(0)} ms` : null,
    info: parts.join(' | ') || null,
  }
}
</script>

<style scoped>
/* ── trigger badge ── */
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: default;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ccc;
}
.connected .dot {
  background: var(--status-ok);
}
.disconnected .dot {
  background: var(--status-error);
}

/* ── hover card shell ── */
.hover-trigger {
  position: relative;
}
.hover-trigger:hover .hover-card {
  visibility: visible;
  opacity: 1;
  transform: translateY(0);
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
  min-width: 240px;
  padding: 8px 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: var(--shadow-lg);
  font-size: 12px;
  line-height: 1.6;
  white-space: nowrap;
}

/* ── card rows ── */
.card-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}
.card-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
}
.card-value {
  font-variant-numeric: tabular-nums;
  color: var(--text-primary);
}
.status-ok {
  color: var(--status-ok);
}
.status-err {
  color: var(--status-error);
}
.card-divider {
  height: 1px;
  background: var(--border);
  margin: 4px 0;
}

/* ── health-specific ── */
.health-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}
.health-section {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.section-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}
.section-status {
  font-size: 11px;
  font-weight: 500;
}
.section-detail {
  display: flex;
  flex-direction: column;
  font-size: 11px;
  color: var(--text-secondary);
  line-height: 1.6;
}
.detail-item {
  display: inline-flex;
  gap: 4px;
}
.detail-text {
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
