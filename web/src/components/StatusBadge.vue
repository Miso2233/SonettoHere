<template>
  <span class="status-badge" :class="connected ? 'connected' : 'disconnected'">
    <span class="dot"></span>
    {{ connected ? '已连接' : '未连接' }}
  </span>
</template>

<script setup lang="ts">
defineProps<{ connected: boolean }>()
</script>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ccc;
}
.connected .dot {
  background: #7ab87a;
}
.disconnected .dot {
  background: #c97a7a;
}
</style>
