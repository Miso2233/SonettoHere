<template>
  <div class="section-card">
    <!-- 分区头部 -->
    <div class="section-header">
      <span class="section-title">{{ theme }}</span>
      <span class="section-count">{{ items.length }} 条</span>
    </div>

    <!-- 条目内容 -->
    <div class="section-body">
      <p class="item-text">{{ currentItem.description }}</p>

      <button
        v-if="currentItem.history.length > 1"
        class="btn-history"
        @click="toggleHistory"
      >
        {{ showHistory ? '收起修改历史' : '查看修改历史' }}
      </button>

      <!-- 修改历史 -->
      <div v-if="showHistory" class="history-list">
        <div v-for="(h, i) in currentItem.history" :key="i" class="history-entry">
          <span class="history-time">{{ h.time }}</span>
          <span class="history-desc">{{ h.description }}</span>
        </div>
      </div>
    </div>

    <!-- 底部导航 -->
    <div class="section-footer">
      <button
        class="btn-nav"
        :disabled="currentIndex === 0"
        @click="prev"
      >
        上一条
      </button>
      <span class="nav-position">{{ currentIndex + 1 }} / {{ items.length }}</span>
      <button
        class="btn-nav"
        :disabled="currentIndex === items.length - 1"
        @click="next"
      >
        下一条
      </button>
    </div>
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
const showHistory = ref(false)

/** 当前条目 */
const currentItem = computed<VignetteMemoryItem>(() => props.items[currentIndex.value])

function prev() {
  if (currentIndex.value > 0) {
    currentIndex.value--
    showHistory.value = false
  }
}

function next() {
  if (currentIndex.value < props.items.length - 1) {
    currentIndex.value++
    showHistory.value = false
  }
}

function toggleHistory() {
  showHistory.value = !showHistory.value
}
</script>

<style scoped>
.section-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}

/* ── 分区头部 ── */
.section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border);
}
.section-title {
  flex: 1;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}
.section-count {
  font-size: 13px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

/* ── 条目内容区 ── */
.section-body {
  padding: 20px;
}
.item-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}

/* ── 历史按钮 ── */
.btn-history {
  display: inline-block;
  margin-top: 16px;
  padding: 4px 14px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: var(--text-tertiary);
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.btn-history:hover {
  background: var(--bg-secondary);
  color: var(--text-secondary);
}

/* ── 历史列表 ── */
.history-list {
  margin-top: 16px;
  padding: 14px 16px;
  background: var(--bg-secondary);
  border-radius: 8px;
}
.history-entry {
  display: flex;
  gap: 12px;
  padding: 6px 0;
  font-size: 13px;
  line-height: 1.6;
}
.history-entry + .history-entry {
  border-top: 1px dashed var(--border);
  padding-top: 10px;
  margin-top: 4px;
}
.history-time {
  flex-shrink: 0;
  color: var(--text-tertiary);
  font-size: 12px;
  min-width: 140px;
}
.history-desc {
  color: var(--text-secondary);
}

/* ── 底部导航 ── */
.section-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px 20px;
}
.btn-nav {
  padding: 4px 12px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-nav:hover:not(:disabled) {
  background: var(--bg-secondary);
  color: var(--text-primary);
}
.btn-nav:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
.nav-position {
  font-size: 12px;
  color: var(--text-tertiary);
}
</style>
