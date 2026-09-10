<template>
  <div class="edit-pair">
    <div class="edit-line edit-old">− {{ oldString }}</div>
    <div class="edit-line edit-new">+ {{ newString }}</div>
  </div>
</template>

<script setup lang="ts">
/** 单笔替换的对照行（− 旧内容 / + 新内容），供确认气泡与结果气泡共用。
 *
 * 全灰阶配色：不靠红绿区分增删，改由「明度差 + 字重差 + 左侧竖条 + 删除线」承载，
 * − / + 前缀（U+2212）继续表意。
 */
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
  padding: 1px 6px;
  border-left: 2px solid transparent;
}

.edit-old {
  color: var(--text-tertiary);
  background: color-mix(in srgb, var(--accent) 3%, transparent);
  border-left-color: var(--border);
  text-decoration: line-through;
  text-decoration-color: var(--text-tertiary);
}

.edit-new {
  color: var(--text-primary);
  background: color-mix(in srgb, var(--accent) 7%, transparent);
  border-left-color: var(--text-primary);
  font-weight: 500;
}
</style>
