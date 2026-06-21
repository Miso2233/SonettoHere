<template>
  <div class="card-lineframe">
    <!-- 头部 -->
    <div class="lf-header">
      <div class="lf-header-left">
        <div class="lf-tool-label">Labels · {{ total }}</div>
        <div class="lf-timestamp">{{ total === 0 ? '未定义标签' : '' }}</div>
      </div>
      <div class="lf-header-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z"/>
          <line x1="7" y1="7" x2="7.01" y2="7"/>
        </svg>
      </div>
    </div>

    <!-- 标签网格 -->
    <div v-if="labels.length" class="label-grid">
      <span v-for="l in labels" :key="l.label_id" class="lg-tag">
        <span class="lg-dot" :style="{ background: dotColor(l.color) }"></span>
        {{ l.name }}
      </span>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">暂无标签</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ toolData?: Record<string, any> }>()

const total = computed(() => props.toolData?.total ?? 0)
const labels = computed<Array<Record<string, any>>>(() => {
  const list = props.toolData?.labels
  return Array.isArray(list) ? list : []
})

const COLOR_MAP: Record<string, string> = {
  berry_red: '#6b7280', red: '#6b7280', orange: '#9ca3af',
  yellow: '#9ca3af', olive_green: '#9ca3af', lime_green: '#9ca3af',
  green: '#9ca3af', mint_green: '#d1d5db', teal: '#9ca3af',
  sky_blue: '#d1d5db', light_blue: '#d1d5db', blue: '#6b7280',
  grape: '#6b7280', violet: '#6b7280', lavender: '#d1d5db',
  magenta: '#6b7280', salmon: '#9ca3af', charcoal: '#333333',
  grey: '#d1d5db', taupe: '#9ca3af',
}

function dotColor(color: string | null | undefined): string {
  return COLOR_MAP[color ?? ''] ?? '#d1d5db'
}
</script>

<style scoped>
.card-lineframe {
  border: 1px solid var(--border);
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  background: var(--bg-primary);
  border-radius: 2px;
}
.lf-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.lf-header-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.lf-tool-label {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--text-secondary);
}
.lf-timestamp {
  font-size: 10px;
  color: var(--text-tertiary, #bbb);
  letter-spacing: 0.3px;
}
.lf-header-icon {
  width: 32px;
  height: 32px;
  color: var(--text-secondary);
  flex-shrink: 0;
}
.lf-header-icon svg {
  width: 100%;
  height: 100%;
}

/* ── 标签列表 ── */
.label-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.lg-tag {
  font-size: 11px;
  color: var(--text-secondary);
  border: 1px solid var(--border);
  padding: 4px 12px;
  border-radius: 2px;
  letter-spacing: 0.3px;
}
.lg-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}

/* ── 空状态 ── */
.empty-state {
  text-align: center;
  padding: 24px 0;
  font-size: 12px;
  color: var(--text-tertiary, #ccc);
  letter-spacing: 0.3px;
}
</style>
