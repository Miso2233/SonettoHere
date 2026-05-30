<template>
  <div class="news-view">
    <!-- 标题栏 -->
    <div class="header">
      <h2>更新动态</h2>
      <span class="news-count" v-if="!loading">共 {{ news.length }} 条更新</span>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading">加载中...</div>

    <!-- 空状态 -->
    <div v-else-if="news.length === 0" class="empty">暂无更新动态</div>

    <!-- 卡片网格 -->
    <div v-else class="card-grid">
      <NewsCard v-for="entry in news" :key="entry.id" :entry="entry" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { api } from '@/api'
import type { NewsEntry } from '@/types'
import NewsCard from '@/components/NewsCard.vue'
import { onMounted, ref } from 'vue'

const news = ref<NewsEntry[]>([])
const loading = ref(false)

async function loadNews() {
  loading.value = true
  try {
    const res = await api.listNews()
    news.value = res.news
  } catch (e: any) {
    console.error('加载更新动态失败', e)
  } finally {
    loading.value = false
  }
}

onMounted(loadNews)
</script>

<style scoped>
.news-view {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.header h2 {
  font-size: 20px;
  font-weight: 700;
}

.news-count {
  font-size: 13px;
  color: var(--text-secondary);
}

.loading,
.empty {
  text-align: center;
  color: var(--text-secondary);
  padding: 40px 0;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
</style>
