<template>
  <div class="section-card" :class="{ 'is-expanded': expanded }">
    <!-- 分区头部 -->
    <div class="section-header" @click="toggle">
      <span class="section-icon">{{ icon }}</span>
      <span class="section-title">{{ theme }}</span>
      <span class="section-count">{{ items.length }} 条</span>
      <span v-if="isCollapsible" class="section-chevron">{{ expanded ? '▲' : '▼' }}</span>
    </div>

    <!-- 条目列表（折叠/展开） -->
    <div
      class="section-collapse"
      :class="{ collapsed: isCollapsed }"
      :style="collapseStyle"
    >
      <div class="section-items">
        <div
          v-for="(item, index) in visibleItems"
          :key="item.id"
          class="memory-item"
          :class="{ 'is-last': index === visibleItems.length - 1 }"
        >
          <p class="item-text">{{ item.description }}</p>
          <button
            v-if="item.history.length > 1"
            class="btn-history"
            @click.stop="toggleHistory(item.id)"
          >
            {{ expandedHistoryId === item.id ? '收起历史' : '查看修改历史' }}
          </button>
          <div v-if="expandedHistoryId === item.id" class="history-list">
            <div v-for="(h, i) in item.history" :key="i" class="history-entry">
              <span class="history-time">{{ h.time }}</span>
              <span class="history-desc">{{ h.description }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部操作区 -->
      <div v-if="isCollapsible" class="section-footer">
        <button class="btn-expand" @click="toggle">
          {{ expanded ? '收起' : `查看全部 ${items.length} 条` }}
        </button>
      </div>
      <div v-else class="section-footer section-footer--static">
        <span>共 {{ items.length }} 条</span>
      </div>
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

const MAX_PREVIEW = 2
const expanded = ref(false)
const expandedHistoryId = ref<string | null>(null)

/** 是否需要折叠功能（条目数 > 2） */
const isCollapsible = computed(() => props.items.length > MAX_PREVIEW)

/** 当前是否处于折叠态 */
const isCollapsed = computed(() => isCollapsible.value && !expanded.value)

/** 当前可见的条目 */
const visibleItems = computed(() => {
  if (expanded.value || !isCollapsible.value) {
    return props.items
  }
  return props.items.slice(0, MAX_PREVIEW)
})

/** 折叠动画内联样式，仅折叠时限制高度 */
const collapseStyle = computed(() => {
  if (!isCollapsed.value) return {}
  return { maxHeight: '180px' }
})

/** 分区图标 */
const THEME_ICONS: Record<string, string> = {
  '身份': '👤',
  '音乐': '🎵',
  '品味': '🎨',
  '地点与路径': '📍',
  '瞬间': '💭',
  '时效待办': '⏰',
}
const icon = computed(() => THEME_ICONS[props.theme] || '📌')

function toggle() {
  if (!isCollapsible.value) return
  expanded.value = !expanded.value
}

function toggleHistory(id: string) {
  expandedHistoryId.value = expandedHistoryId.value === id ? null : id
}
</script>

<style scoped>
.section-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  transition: box-shadow 0.2s;
}
.section-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

/* ── 分区头部 ── */
.section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}
.section-header:hover {
  background: var(--bg-secondary);
}
.section-icon {
  font-size: 20px;
  line-height: 1;
  flex-shrink: 0;
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
.section-chevron {
  font-size: 11px;
  color: var(--text-tertiary);
  flex-shrink: 0;
  transition: transform 0.3s;
}

/* ── 折叠动画容器 ── */
.section-collapse {
  overflow: hidden;
  transition: max-height 0.35s ease;
}
.section-collapse.collapsed {
  max-height: 180px;
}
.section-collapse:not(.collapsed) {
  max-height: 6000px;
}

/* ── 条目列表 ── */
.section-items {
  padding: 0 20px;
}
.memory-item {
  padding: 12px 0;
  border-bottom: 1px solid var(--border);
}
.memory-item.is-last {
  border-bottom: none;
  padding-bottom: 4px;
}
.item-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}

/* ── 历史按钮 ── */
.btn-history {
  display: inline-block;
  margin-top: 6px;
  padding: 2px 10px;
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
  margin-top: 8px;
  padding: 10px 12px;
  background: var(--bg-secondary);
  border-radius: 8px;
}
.history-entry {
  display: flex;
  gap: 10px;
  padding: 4px 0;
  font-size: 13px;
  line-height: 1.6;
}
.history-entry + .history-entry {
  border-top: 1px dashed var(--border);
  padding-top: 8px;
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

/* ── 底部操作区 ── */
.section-footer {
  padding: 12px 20px 16px;
}
.section-footer--static {
  padding-top: 4px;
  font-size: 13px;
  color: var(--text-tertiary);
}
.btn-expand {
  display: block;
  width: 100%;
  padding: 8px;
  border: 1px dashed var(--border);
  border-radius: 8px;
  background: transparent;
  color: var(--text-tertiary);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.btn-expand:hover {
  background: var(--bg-secondary);
  color: var(--text-secondary);
  border-color: var(--text-tertiary);
}
</style>
