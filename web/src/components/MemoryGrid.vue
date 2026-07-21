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

      <!-- 统计环形图 -->
      <div class="donut-row">
        <div class="donut-cell" v-for="s in stats" :key="s.label">
          <svg viewBox="0 0 80 80" width="80" height="80">
            <circle cx="40" cy="40" r="28" fill="none" stroke="var(--border)" stroke-width="5" />
            <circle
              cx="40" cy="40" r="28" fill="none"
              stroke="var(--accent)" stroke-width="5" stroke-linecap="round"
              :stroke-dasharray="s.dashArray"
              transform="rotate(-90 40 40)"
            />
            <text x="40" y="36" text-anchor="middle" fill="var(--text-primary)"
              font-size="16" font-weight="700">{{ s.value }}</text>
            <text x="40" y="50" text-anchor="middle" fill="var(--text-tertiary)"
              font-size="9">{{ s.unit }}</text>
          </svg>
          <div class="donut-label">{{ s.label }}</div>
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
          :style="{ gridRow: 'span ' + sectionRowSpan(section) }"
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
              <div v-for="item in section.items" :key="item.id" class="memory-item">
                <div class="item-meta">
                  <span class="item-tag">{{ item.id }}</span>
                  <span class="item-hit">📌 <strong>{{ item.hit }}</strong></span>
                  <span class="item-time">{{ item._sort_time }}</span>
                  <span
                    v-if="item.history && item.history.length > 0"
                    class="item-history-toggle"
                    @click="toggleHistory(item.id)"
                  >📜</span>
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
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { api } from '@/api'
import type { VignetteSection } from '@/types'

// ── 状态 ──
const loading = ref(true)
const sections = ref<VignetteSection[]>([])
const searchQuery = ref('')
const expandedHistory = ref<string | null>(null)
const searchRef = ref<HTMLInputElement>()

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

const R = 28
const CIRCUM = 2 * Math.PI * R

function dash(ratio: number): string {
  const clamped = Math.min(ratio, 1)
  return `${clamped * CIRCUM} ${(1 - clamped) * CIRCUM}`
}

const stats = computed(() => [
  { value: totalItems.value, unit: '条', label: '记忆条目', dashArray: dash(totalItems.value / 50) },
  { value: sections.value.length, unit: '个', label: '分区', dashArray: dash(sections.value.length / 10) },
  { value: totalHits.value, unit: '次', label: '总引用', dashArray: dash(totalHits.value / 100) },
  { value: parseFloat(avgHits.value), unit: '次', label: '均引用', dashArray: dash(parseFloat(avgHits.value) / 10) },
])

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

function sectionRowSpan(section: VignetteSection): number {
  const len = section.items.length
  if (len <= 2) return 1
  if (len <= 4) return 2
  return 3
}

function toggleHistory(id: string) {
  expandedHistory.value = expandedHistory.value === id ? null : id
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

/* ── 统计环形图 ── */
.donut-row {
  display: flex;
  justify-content: center;
  gap: 32px;
  margin-bottom: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 8px;
}
.donut-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}
.donut-label {
  font-size: 11px;
  color: var(--text-tertiary);
}

/* ── 网格 ── */
.grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
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
.recent-widget { grid-column: span 2; grid-row: span 1; }
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
  .donut-row { gap: 12px; flex-wrap: wrap; }
  .donut-cell { width: 80px; }
}
</style>
