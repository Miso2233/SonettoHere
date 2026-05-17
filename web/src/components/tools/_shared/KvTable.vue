<template>
  <div class="kv-list">
    <div class="kv-row" v-for="(item, idx) in pairs" :key="idx">
      <span class="kv-key">{{ item.key }}</span>
      <span class="kv-value" v-if="item.primitive">{{ item.value }}</span>
      <pre class="kv-nested" v-else>{{ item.value }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
interface KvPair {
  key: string
  value: string
  primitive: boolean
}

defineProps<{ pairs: KvPair[] }>()
</script>

<style scoped>
.kv-list {
  background: var(--bg-primary);
  border-radius: 6px;
  padding: 8px 14px;
}

.kv-row {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  padding: 3px 0;
  line-height: 1.6;
}

.kv-key {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  color: var(--text-secondary);
  flex-shrink: 0;
  min-width: 6em;
}

.kv-key::after {
  content: ':';
}

.kv-value {
  font-size: 13px;
  color: var(--text-primary);
  word-break: break-word;
}

.kv-nested {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 11px;
  line-height: 1.5;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  background: var(--bg-secondary);
  padding: 6px 10px;
  border-radius: 4px;
  flex: 1;
  max-height: 120px;
  overflow-y: auto;
}
</style>
