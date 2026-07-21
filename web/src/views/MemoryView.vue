<template>
  <div class="memory-view">
    <MemoryGrid />
  </div>
</template>

<script setup lang="ts">
import MemoryGrid from '@/components/MemoryGrid.vue'
</script>

<style scoped>
.memory-view {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}
</style>
