<template>
  <div class="memory-panel">
    <MomentCard />

    <!-- Vignette 瀑布流（默认启用） -->
    <template v-if="useVignette">
      <!-- 骨架屏：加载中且无数据 -->
      <div v-if="loading && sections.length === 0" class="skeleton-container">
        <div v-for="i in 3" :key="i" class="skeleton-card">
          <div class="skeleton-pulse"></div>
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
        <div v-else-if="narrative">
          <RenderMarkdown :content="narrative" />
        </div>
        <div v-else class="memory-empty">
          暂无记忆叙事。开始一段对话后，AI 会自动生成关于你的记忆。
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api'
import type { VignetteSection } from '@/types'
import MomentCard from '@/components/MomentCard.vue'
import SectionCard from '@/components/SectionCard.vue'
import RenderMarkdown from '@/components/RenderMarkdown.vue'

/** 可通过开发者工具切换为 false 回退到 Markdown 渲染 */
const useVignette = ref(true)

const narrative = ref('')
const sections = ref<VignetteSection[]>([])
const loading = ref(false)

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

/* ── 瀑布流容器 ── */
.sections-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 12px;
}

/* ── 骨架屏 ── */
.skeleton-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.skeleton-card {
  height: 80px;
  border-radius: var(--radius);
  background: var(--bg-card);
  border: 1px solid var(--border);
  padding: 20px;
}
.skeleton-pulse {
  width: 60%;
  height: 16px;
  background: var(--bg-secondary);
  border-radius: 4px;
  animation: skeleton-fade 1.8s ease-in-out infinite;
}

@keyframes skeleton-fade {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 0.9; }
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
