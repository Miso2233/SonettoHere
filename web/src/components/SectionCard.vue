<template>
  <div class="section-card">
    <!-- 分区头部 + 导航，合并为一行 -->
    <div class="section-header">
      <span class="section-title">{{ theme }}</span>
      <span class="section-nav">
        <button
          class="nav-link"
          :disabled="currentIndex === 0"
          @click="prev"
        >←</button>
        <button
          class="nav-link"
          :disabled="currentIndex === items.length - 1"
          @click="next"
        >→</button>
      </span>
    </div>

    <!-- 条目内容 -->
    <p class="item-text">{{ currentItem.description }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { VignetteMemoryItem } from '@/types'

const props = defineProps<{
  theme: string
  items: VignetteMemoryItem[]
}>()

const currentIndex = ref(0)

const currentItem = computed<VignetteMemoryItem>(() => props.items[currentIndex.value])

function prev() {
  if (currentIndex.value > 0) currentIndex.value--
}
function next() {
  if (currentIndex.value < props.items.length - 1) currentIndex.value++
}
</script>

<style scoped>
.section-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}

/* ── 头部行：主题 + 导航 ── */
.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px 0;
}
.section-title {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.section-nav {
  display: flex;
  gap: 2px;
}
.nav-link {
  padding: 2px 6px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--text-tertiary);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.nav-link:hover:not(:disabled) {
  background: var(--bg-secondary);
  color: var(--text-primary);
}
.nav-link:disabled {
  opacity: 0.2;
  cursor: not-allowed;
}

/* ── 内容 ── */
.item-text {
  margin: 0;
  padding: 12px 16px 16px;
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
