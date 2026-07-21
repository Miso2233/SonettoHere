<template>
  <div class="memory-grid">
    <!-- ── 加载态 ── -->
    <template v-if="loading">
      <div class="loading-bar">加载记忆网格…</div>
    </template>

    <!-- ── 空态 ── -->
    <template v-else-if="sections.length === 0">
      <div class="empty-state">
        <div class="empty-icon">🧠</div>
        <p>还没有记忆，开始对话吧。</p>
      </div>
    </template>

    <!-- ── 数据 ── -->
    <template v-else>
      <!-- 搜索条 -->
      <div class="search-widget">
        <span class="search-icon">🔍</span>
        <input
          ref="searchRef"
          v-model="searchQuery"
          type="text"
          placeholder="在所有记忆中搜索…"
          @input="onSearch"
        />
        <span class="search-count">{{ filteredSections.reduce((s, sec) => s + sec.items.length, 0) }}/{{ sections.reduce((s, sec) => s + sec.items.length, 0) }}</span>
      </div>

      <!-- 统计栏：左标题 + 右环形图与数字 -->
      <div class="stats-bar">
        <div class="stats-brand">
          <span class="stats-title">Memory</span>
          <span class="stats-subtitle">Remembered For You</span>
        </div>
        <div class="stats-metrics">
          <div class="stats-donut">
            <svg viewBox="0 0 120 120" width="104" height="104" class="donut-svg">
              <circle cx="60" cy="60" r="42" fill="none" stroke="var(--border)" stroke-width="12" />
              <circle
                cx="60" cy="60" r="42" fill="none"
                stroke="var(--accent)" stroke-width="12"
                :stroke-dasharray="avgDash"
                transform="rotate(-90 60 60)"
              />
            </svg>
            <div class="donut-text">
              <span class="donut-value">{{ avgHits }}</span>
              <span class="donut-unit">均引用</span>
            </div>
          </div>
          <div class="stats-figures">
            <div class="stat-figure">
              <span class="figure-num">{{ totalItems }}</span>
              <span class="figure-label">记忆条目</span>
            </div>
            <div class="stat-figure">
              <span class="figure-num">{{ sections.length }}</span>
              <span class="figure-label">分区</span>
            </div>
            <div class="stat-figure">
              <span class="figure-num">{{ totalHits }}</span>
              <span class="figure-label">总引用</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 二维网格 -->
      <div class="grid">
        <!-- 热门记忆 -->
        <div v-if="hotMemories.length" class="widget hot-widget">
          <div class="widget-header">
            <span class="widget-title">🔥 热门记忆</span>
            <span class="widget-badge">引用最多</span>
          </div>
          <div class="widget-body">
            <div class="hot-list">
              <div v-for="(item, i) in hotMemories" :key="'hot-' + i" class="hot-item">
                <span class="hot-rank" :class="'rank-' + (i + 1)">{{ i + 1 }}</span>
                <span class="hot-desc">{{ item.description }}</span>
                <span class="hot-num">📌 {{ item.hit }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 最近活动 -->
        <div v-if="recentMemories.length" class="widget recent-widget">
          <div class="widget-header">
            <span class="widget-title">🕐 最近活动</span>
            <span class="widget-badge">最新更新</span>
          </div>
          <div class="widget-body">
            <div class="timeline">
              <div v-for="item in recentMemories" :key="'recent-' + item.id" class="tl-item">
                <div class="tl-time">{{ item._sort_time }}</div>
                <div class="tl-desc">{{ item.description }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 分区卡片 -->
        <div
          v-for="(section, si) in filteredSections"
          :key="'sec-' + si"
          class="widget section-widget"
        >
          <div class="widget-header">
            <span class="widget-title">
              <span class="theme-dot" :style="{ background: themeColor(si) }"></span>
              {{ section.theme }}
            </span>
            <span class="widget-badge">{{ section.items.length }}</span>
          </div>
          <div class="widget-body">
            <div class="memory-list">
              <div v-for="item in visibleItems(section, si)" :key="item.id" class="memory-item">
                <div class="item-meta">
                  <span class="item-tag">{{ item.id }}</span>
                  <span class="item-hit">📌 <strong>{{ item.hit }}</strong></span>
                  <span class="item-time">{{ item._sort_time }}</span>
                  <span
                    v-if="item.history && item.history.length > 0"
                    class="item-history-toggle"
                    @click="toggleHistory(item.id)"
                  >📜</span>
                  <span class="item-delete" @click="handleDelete(item.id, $event)">✕</span>
                </div>
                <div class="item-desc" v-html="highlight(item.description)"></div>
                <div
                  v-if="item.history && item.history.length > 0 && expandedHistory === item.id"
                  class="history-pop"
                >
                  <div v-for="(h, hi) in item.history" :key="'h-' + hi" class="h-row">
                    <span class="h-text">{{ h.description }}</span>
                    <span class="h-time">{{ h.time }}</span>
                  </div>
                </div>
              </div>
            </div>
            <button
              v-if="section.items.length > MAX_VISIBLE"
              class="expand-btn"
              @click="toggleSection(si)"
            >{{ expandedSections.includes(si) ? '收起' : `展开全部 ${section.items.length} 条` }}</button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { api } from '@/api'
import type { VignetteSection } from '@/types'

// ── 状态 ──
const loading = ref(true)
const sections = ref<VignetteSection[]>([])
const searchQuery = ref('')
const expandedHistory = ref<string | null>(null)
const searchRef = ref<HTMLInputElement>()
const expandedSections = ref<number[]>([])

const MAX_VISIBLE = 20

// ── 数据加载 ──
async function loadMemories() {
  loading.value = true
  try {
    const res = await api.getMemories()
    sections.value = res.sections || []
  } catch {
    sections.value = []
  } finally {
    loading.value = false
  }
}

// ── 统计计算 ──
const allItems = computed(() => sections.value.flatMap(s => s.items))
const totalItems = computed(() => allItems.value.length)
const totalHits = computed(() => allItems.value.reduce((s, i) => s + (i.hit || 0), 0))
const avgHits = computed(() => {
  const n = totalItems.value
  return n ? (totalHits.value / n).toFixed(1) : '0'
})

const avgR = 42
const avgCircum = 2 * Math.PI * avgR
const avgDash = computed(() => {
  const val = parseFloat(avgHits.value)
  const r = Math.min(val / 10, 1)
  return `${r * avgCircum} ${(1 - r) * avgCircum}`
})

// ── 搜索 ──
const filteredSections = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return sections.value
  return sections.value
    .map(s => ({
      ...s,
      items: s.items.filter(i => i.description.toLowerCase().includes(q)),
    }))
    .filter(s => s.items.length > 0)
})

function onSearch() {
  // 高亮重新渲染，无需额外操作
}

// ── 热门记忆 Top 3 ──
const hotMemories = computed(() =>
  [...allItems.value]
    .sort((a, b) => (b.hit || 0) - (a.hit || 0))
    .slice(0, 3)
)

// ── 最近活动 Top 5 ──
const recentMemories = computed(() =>
  [...allItems.value]
    .sort((a, b) => b._sort_time.localeCompare(a._sort_time))
    .slice(0, 5)
)

// ── 辅助 ──
const THEME_COLORS = ['#000', '#444', '#666', '#888', '#aaa', '#bbb', '#ccc']

function themeColor(index: number): string {
  return THEME_COLORS[index % THEME_COLORS.length]
}

function toggleHistory(id: string) {
  expandedHistory.value = expandedHistory.value === id ? null : id
}

function visibleItems(section: VignetteSection, index: number) {
  if (expandedSections.value.includes(index)) return section.items
  return section.items.slice(0, MAX_VISIBLE)
}

async function handleDelete(id: string, event: MouseEvent) {
  event.stopPropagation()
  if (!confirm(`确定删除记忆「${id}」？`)) return
  try {
    await api.deleteMemory(id)
    const res = await api.getMemories()
    sections.value = res.sections || []
  } catch (e: any) {
    alert('删除失败: ' + (e.message || e))
  }
}

function toggleSection(index: number) {
  if (expandedSections.value.includes(index)) {
    expandedSections.value = expandedSections.value.filter(i => i !== index)
  } else {
    expandedSections.value = [...expandedSections.value, index]
  }
}

function highlight(text: string): string {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return escapeHtml(text)
  const re = new RegExp('(' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi')
  return escapeHtml(text).replace(new RegExp(escapeHtml(q), 'gi'), m => '<mark>' + m + '</mark>')
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

onMounted(loadMemories)
</script>

<style scoped>
.memory-grid {
  max-width: 1200px;
  margin: 0 auto;
}

/* ── 加载态 ── */
.loading-bar {
  text-align: center;
  padding: 40px 0;
  color: var(--text-tertiary);
  font-size: 14px;
}

/* ── 空态 ── */
.empty-state {
  text-align: center;
  padding: 60px 20px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}
.empty-icon { font-size: 36px; margin-bottom: 10px; }
.empty-state p { font-size: 14px; color: var(--text-tertiary); }

/* ── 搜索条 ── */
.search-widget {
  display: flex; align-items: center;
  padding: 8px 10px 8px 18px;
  margin-bottom: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  gap: 10px;
}
.search-icon { color: var(--text-tertiary); font-size: 15px; }
.search-widget input {
  flex: 1; border: none; outline: none; font-size: 14px;
  color: var(--text-primary); background: transparent;
  font-family: inherit;
}
.search-widget input::placeholder { color: var(--text-tertiary); }
.search-count {
  font-size: 12px; color: var(--text-tertiary); white-space: nowrap;
  padding: 2px 10px; background: var(--bg-secondary);
  border-radius: 999px;
}

/* ── 统计栏：左环形图 + 右数字 ── */
.stats-bar {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-bottom: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px 24px;
}
.stats-brand {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.stats-title {
  font-size: 40px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.8px;
  line-height: 1.05;
}
.stats-subtitle {
  font-size: 14px;
  color: var(--text-tertiary);
  font-weight: 400;
  letter-spacing: 0.4px;
}
.stats-metrics {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-left: auto;
}
.stats-donut {
  flex-shrink: 0;
  position: relative;
  width: 104px;
  height: 104px;
}
.donut-svg {
  display: block;
}
.donut-text {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}
.donut-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}
.donut-unit {
  font-size: 11px;
  color: var(--text-tertiary);
  line-height: 1;
}
.stats-figures {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.stat-figure {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.figure-num {
  font-size: 18px;
  font-weight: 700;
  color: var(--accent);
  letter-spacing: -0.3px;
  min-width: 3ch;
}
.figure-label {
  font-size: 13px;
  color: var(--text-tertiary);
}

/* ── 网格 ── */
.grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  align-items: start;
}

/* ── 通用组件 ── */
.widget {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  transition: box-shadow 0.2s;
}
.widget:hover {
  box-shadow: 0 2px 12px rgba(0,0,0,0.06);
}
.hot-widget { grid-column: span 2; grid-row: span 2; }
.recent-widget { grid-column: span 2; grid-row: span 2; }
.section-widget { grid-column: span 1; }

.widget-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-secondary);
}
.widget-title {
  font-size: 12px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.4px; color: var(--text-tertiary);
  display: flex; align-items: center; gap: 6px;
}
.widget-badge {
  font-size: 10px; padding: 1px 8px; border-radius: 999px;
  background: var(--bg-card); color: var(--text-tertiary);
  font-weight: 500; border: 1px solid var(--border);
}
.widget-body { padding: 10px 14px; }

/* ── 热门记忆 ── */
.hot-list { display: flex; flex-direction: column; gap: 8px; }
.hot-item {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px; border-radius: 6px;
  background: var(--bg-secondary);
}
.hot-rank {
  width: 22px; height: 22px; display: flex; align-items: center;
  justify-content: center; border-radius: 999px;
  font-size: 11px; font-weight: 700; flex-shrink: 0;
  background: var(--border); color: var(--text-tertiary);
}
.hot-rank.rank-1 { background: #1a1a1a; color: #fff; }
.hot-rank.rank-2 { background: #555; color: #fff; }
.hot-rank.rank-3 { background: #999; color: #fff; }
.hot-desc {
  flex: 1; font-size: 13px; line-height: 1.5;
  overflow: hidden; text-overflow: ellipsis;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}
.hot-num { font-size: 11px; color: var(--text-tertiary); white-space: nowrap; }

/* ── 时间线 ── */
.timeline { position: relative; padding-left: 16px; }
.timeline::before {
  content: ''; position: absolute; left: 4px; top: 4px; bottom: 4px;
  width: 1px; background: var(--border);
}
.tl-item { position: relative; margin-bottom: 12px; }
.tl-item:last-child { margin-bottom: 0; }
.tl-item::before {
  content: ''; position: absolute; left: -12px; top: 5px;
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--accent); border: 2px solid var(--bg-card);
}
.tl-time { font-size: 11px; color: var(--text-tertiary); margin-bottom: 2px; }
.tl-desc { font-size: 13px; line-height: 1.5; color: var(--text-primary); }

/* ── 分区条目 ── */
.memory-list { display: flex; flex-direction: column; gap: 6px; }
.memory-item {
  padding: 8px 10px; border-radius: 6px;
  background: var(--bg-secondary);
}
.item-meta {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 3px; font-size: 11px; color: var(--text-tertiary);
}
.item-tag {
  font-family: 'SF Mono', 'Consolas', monospace; font-size: 10px;
  padding: 1px 5px; border-radius: 3px;
  background: var(--bg-card); color: var(--text-tertiary);
  border: 1px solid var(--border);
}
.item-hit strong { color: var(--text-secondary); }
.item-time { color: var(--text-tertiary); }
.item-history-toggle {
  cursor: pointer; margin-left: auto;
  opacity: 0.5; transition: opacity 0.12s;
}
.item-history-toggle:hover { opacity: 1; }
.item-delete {
  cursor: pointer;
  opacity: 0;
  font-size: 12px;
  color: var(--text-tertiary);
  transition: opacity 0.12s, color 0.12s;
  padding: 0 4px;
}
.memory-item:hover .item-delete {
  opacity: 0.5;
}
.item-delete:hover {
  color: var(--status-error) !important;
  opacity: 1 !important;
}
.item-desc {
  font-size: 13px; line-height: 1.6; color: var(--text-primary);
}
.item-desc :deep(mark) {
  background: #fef9c3; color: #854d0e; border-radius: 2px; padding: 0 2px;
}

/* ── 历史追溯 ── */
.history-pop {
  margin-top: 6px; padding: 6px 8px; background: var(--bg-card);
  border-radius: 4px; font-size: 12px; line-height: 1.6;
  border-left: 2px solid var(--border);
}
.h-row {
  padding: 3px 0; border-bottom: 1px solid var(--border);
  color: var(--text-secondary);
}
.h-row:last-child { border-bottom: none; }
.h-time { font-size: 10px; color: var(--text-tertiary); margin-left: 6px; }

/* ── 展开按钮 ── */
.expand-btn {
  display: block;
  width: 100%;
  margin-top: 6px;
  padding: 6px 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}
.expand-btn:hover {
  background: var(--bg-secondary);
  color: var(--text-primary);
}

/* ── 圆点 ── */
.theme-dot {
  display: inline-block; width: 6px; height: 6px; border-radius: 50%;
  flex-shrink: 0;
}

/* ── 响应式 ── */
@media (max-width: 900px) {
  .grid { grid-template-columns: repeat(2, 1fr); }
  .hot-widget { grid-column: span 2; grid-row: span 1; }
  .recent-widget { grid-column: span 2; }
  .section-widget { grid-column: span 1; }
}
@media (max-width: 560px) {
  .grid { grid-template-columns: 1fr; }
  .hot-widget,
  .recent-widget,
  .section-widget { grid-column: 1; }
  .stats-bar { flex-direction: column; align-items: flex-start; gap: 16px; }
  .stats-metrics { margin-left: 0; }
}
</style>
