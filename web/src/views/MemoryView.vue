<template>
  <div class="memory-view">
    <MemoryPanel />
  </div>
</template>

<script setup lang="ts">
import MemoryPanel from '@/components/MemoryPanel.vue'
</script>

<style scoped>
.memory-view {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}
</style>
