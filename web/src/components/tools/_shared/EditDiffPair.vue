<template>
  <div class="edit-pair">
    <div class="edit-line edit-old">− {{ oldString }}</div>
    <div class="edit-line edit-new">+ {{ newString }}</div>
  </div>
</template>

<script setup lang="ts">
/** 单笔替换的红绿对照行（− 旧内容 / + 新内容），供确认气泡与结果气泡共用。 */
defineProps<{ oldString: string; newString: string }>()
</script>

<style scoped>
.edit-pair {
  padding: 4px 0;
}

.edit-line {
  font-family: 'SF Mono', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}

.edit-old { color: #c0392b; }
.edit-new { color: #2e7d32; }
</style>
