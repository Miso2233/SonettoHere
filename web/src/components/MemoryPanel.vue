<template>
  <div class="memory-panel">
    <MomentCard />

    <div class="memory-header">
      <h2>记忆分区</h2>
      <button class="btn-refresh" @click="refresh" :disabled="loading">
        {{ loading ? '刷新中……' : '刷新' }}
      </button>
    </div>

    <!-- Vignette 瀑布流（默认启用） -->
    <template v-if="useVignette">
      <!-- 骨架屏：加载中且无数据 -->
      <div v-if="loading && sections.length === 0" class="skeleton-container">
        <div v-for="i in 3" :key="i" class="skeleton-card">
          <div class="skeleton-header"></div>
          <div class="skeleton-row"></div>
          <div class="skeleton-row"></div>
        </div>
      </div>

      <!-- 有数据 -->
      <div v-else-if="sections.length > 0" class="sections-container">
        <SectionCard
          v-for="section in sections"
          :key="section.theme"
          :theme="section.theme"
          :items="section.items"
        />
      </div>

      <!-- 空数据 -->
      <div v-else-if="!loading" class="memory-empty">
        还没有记忆，开始对话吧。
      </div>
    </template>

    <!-- 回退：Markdown 叙事（当 Vignette 关闭或出错时） -->
    <template v-else>
      <div class="memory-body">
        <div v-if="loading && !narrative" class="memory-loading">
          加载中……
        </div>
        <div v-else-if="narrative" class="markdown-body" v-html="rendered"></div>
        <div v-else class="memory-empty">
          暂无记忆叙事。开始一段对话后，AI 会自动生成关于你的记忆。
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { renderMarkdown } from '@/utils/markdown'
import { api } from '@/api'
import type { VignetteSection } from '@/types'
import MomentCard from '@/components/MomentCard.vue'
import SectionCard from '@/components/SectionCard.vue'

/** 可通过开发者工具切换为 false 回退到 Markdown 渲染 */
const useVignette = ref(true)

const narrative = ref('')
const sections = ref<VignetteSection[]>([])
const loading = ref(false)

const rendered = computed(() => {
  return renderMarkdown(narrative.value)
})

async function refresh() {
  loading.value = true
  try {
    if (useVignette.value) {
      const res = await api.getMemories()
      sections.value = res.sections
    } else {
      const res = await api.getNarrative()
      narrative.value = res.narrative
    }
  } catch {
    sections.value = []
    narrative.value = ''
  } finally {
    loading.value = false
  }
}

onMounted(() => refresh())
</script>

<style scoped>
.memory-panel {
  max-width: 768px;
  margin: 0 auto;
}

/* ── 头部 ── */
.memory-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 24px;
  margin-bottom: 16px;
}
.memory-header h2 {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}
.btn-refresh {
  padding: 6px 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  transition: background 0.15s;
}
.btn-refresh:hover:not(:disabled) {
  background: var(--bg-secondary);
}

/* ── 瀑布流容器 ── */
.sections-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ── 骨架屏 ── */
.skeleton-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.skeleton-card {
  height: 120px;
  border-radius: var(--radius);
  background: var(--bg-card);
  border: 1px solid var(--border);
  padding: 16px 20px;
}
.skeleton-header {
  width: 40%;
  height: 18px;
  background: var(--bg-secondary);
  border-radius: 4px;
  margin-bottom: 16px;
  animation: shimmer 1.5s ease-in-out infinite;
}
.skeleton-row {
  width: 100%;
  height: 14px;
  background: var(--bg-secondary);
  border-radius: 4px;
  margin-bottom: 10px;
  animation: shimmer 1.5s ease-in-out infinite;
}
.skeleton-row:last-child {
  width: 70%;
}

@keyframes shimmer {
  0% { opacity: 0.6; }
  50% { opacity: 1; }
  100% { opacity: 0.6; }
}

/* ── 空态 / 加载占位（回退路径用） ── */
.memory-body {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px;
}
.memory-body .markdown-body {
  line-height: 1.8;
}
.memory-empty,
.memory-loading {
  color: var(--text-secondary);
  font-size: 14px;
  text-align: center;
  padding: 40px 0;
}
</style>
