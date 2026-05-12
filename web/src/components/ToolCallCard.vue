<template>
  <details class="tool-card" :class="toolCall.status" :open="toolCall.status === 'running'">
    <summary class="tool-header">
      <span class="tool-icon">
        <span v-if="toolCall.status === 'running'" class="spinner-sm"></span>
        <span v-else-if="toolCall.status === 'done'">&#10003;</span>
        <span v-else>&#10007;</span>
      </span>
      <span class="tool-name">{{ toolCall.name }}</span>
      <span class="tool-elapsed" v-if="toolCall.elapsed !== null">
        {{ toolCall.elapsed }}s
      </span>
    </summary>
    <div class="tool-body">
      <div class="tool-section" v-if="toolCall.input && toolCall.input !== '{}'">
        <div class="tool-section-label">参数</div>
        <pre>{{ toolCall.input }}</pre>
      </div>
      <div class="tool-section" v-if="toolCall.output">
        <div class="tool-section-label">结果</div>
        <pre>{{ toolCall.output }}</pre>
      </div>
    </div>
  </details>
</template>

<script setup lang="ts">
import type { ToolCall } from '@/types'

defineProps<{ toolCall: ToolCall }>()
</script>

<style scoped>
.tool-card {
  margin: 8px 0;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-card);
  overflow: hidden;
}
.tool-card.running {
  border-color: var(--accent-light);
}
.tool-card.error {
  border-color: #d4a0a0;
}
.tool-header {
  padding: 8px 14px;
  font-size: 13px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
  list-style: none;
}
.tool-header::-webkit-details-marker {
  display: none;
}
.tool-icon {
  font-size: 12px;
  width: 16px;
  text-align: center;
}
.spinner-sm {
  display: inline-block;
  width: 10px;
  height: 10px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.tool-name {
  font-weight: 600;
  color: var(--text-primary);
}
.tool-elapsed {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-secondary);
}
.tool-body {
  border-top: 1px solid var(--border);
  padding: 8px 14px 12px;
}
.tool-section {
  margin-bottom: 8px;
}
.tool-section:last-child {
  margin-bottom: 0;
}
.tool-section-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.tool-section pre {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  background: var(--bg-primary);
  padding: 8px;
  border-radius: 6px;
  max-height: 200px;
  overflow-y: auto;
}
</style>
