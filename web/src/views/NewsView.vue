<template>
  <div class="news-view">
    <!-- 标题栏 -->
    <div class="header">
      <h2>更新动态</h2>
      <span class="news-count" v-if="!loading">共 {{ news.length }} 条更新</span>
    </div>

    <div class="news-body">
      <!-- 卡片列表 -->
      <div class="news-content">
        <div v-if="loading" class="loading">加载中...</div>
        <div v-else-if="news.length === 0" class="empty">暂无更新动态</div>
        <div v-else class="card-grid" ref="cardGridRef">
          <NewsCard v-for="entry in news" :key="entry.id" :entry="entry" />
        </div>
      </div>

      <!-- 版本演进时间轴 -->
      <div v-if="versionNodes.length > 0" class="version-timeline" :style="tlBounds">
        <div class="tl-track"></div>
        <div
          v-for="node in versionNodes"
          :key="node.version"
          class="tl-node"
          :style="{ top: node.top + 'px' }"
        >
          <div class="tl-dot"></div>
          <span class="tl-label">{{ node.version }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { api } from '@/api'
import type { NewsEntry } from '@/types'
import NewsCard from '@/components/NewsCard.vue'
import { onMounted, onUnmounted, ref } from 'vue'

const news = ref<NewsEntry[]>([])
const loading = ref(false)
const cardGridRef = ref<HTMLElement | null>(null)
const tlBounds = ref<{ top: string; height: string }>()
const versionNodes = ref<{ version: string; top: number }[]>([])

let observer: ResizeObserver | null = null

function updateTimelineBounds() {
  const grid = cardGridRef.value
  const body = grid?.closest<HTMLElement>('.news-body')
  if (!body || !grid) return

  const cards = grid.querySelectorAll<HTMLElement>('.news-card')
  if (cards.length < 2) return

  const bodyRect = body.getBoundingClientRect()
  const firstRect = cards[0].getBoundingClientRect()
  const lastRect = cards[cards.length - 1].getBoundingClientRect()

  const top = firstRect.top + firstRect.height / 2 - bodyRect.top
  const bottom = lastRect.top + lastRect.height / 2 - bodyRect.top

  tlBounds.value = {
    top: top + 'px',
    height: (bottom - top) + 'px',
  }

  // 根据卡片实际 DOM 位置计算版本圆点的 top 值，而非按索引均分
  const tlTop = bodyRect.top + top
  const seen = new Set<string>()
  const nodes: { version: string; top: number }[] = []
  news.value.forEach((entry, idx) => {
    if (seen.has(entry.version)) return
    seen.add(entry.version)
    const card = cards[idx]
    if (!card) return
    const cardRect = card.getBoundingClientRect()
    nodes.push({
      version: entry.version,
      top: cardRect.top + cardRect.height / 2 - tlTop,
    })
  })
  versionNodes.value = nodes
}

async function loadNews() {
  loading.value = true
  try {
    const res = await api.listNews()
    news.value = res.news.sort((a, b) => b.pr_number - a.pr_number)
    requestAnimationFrame(updateTimelineBounds)
  } catch (e: any) {
    console.error('加载更新动态失败', e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadNews()
  observer = new ResizeObserver(updateTimelineBounds)
  observer.observe(document.querySelector('.news-view')!)
})

onUnmounted(() => {
  observer?.disconnect()
})

</script>

<style scoped>
.news-view {
  flex: 1;
  overflow-y: auto;
  padding: 40px 48px;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 28px;
}

.header h2 {
  font-size: 20px;
  font-weight: 700;
}

.news-count {
  font-size: 13px;
  color: var(--text-secondary);
}

.news-body {
  position: relative;
}

.news-content {
  max-width: 720px;
  margin: 0 auto;
}

.loading,
.empty {
  text-align: center;
  color: var(--text-secondary);
  padding: 40px 0;
}

.card-grid {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ── 版本时间轴 ── */

.version-timeline {
  position: absolute;
  left: calc(75% + 180px);
  transform: translateX(-50%);
  width: 80px;
  pointer-events: none;
}

.tl-track {
  position: absolute;
  left: 50%;
  top: 0;
  bottom: 0;
  width: 1px;
  background: var(--border);
  transform: translateX(-50%);
}

.tl-node {
  position: absolute;
  left: 50%;
  display: flex;
  align-items: center;
  gap: 8px;
  transform: translateY(-50%);
}

.tl-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-primary);
  flex-shrink: 0;
  position: relative;
  left: -4px;
}

.tl-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  font-family: 'SF Mono', 'Consolas', monospace;
  white-space: nowrap;
  padding-left: 12px;
}
</style>
