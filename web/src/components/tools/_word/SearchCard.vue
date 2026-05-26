<template>
  <div class="word-card search-card">
    <div class="card-header">
      <span class="search-icon">🔍</span>
      <div>
        <div class="card-title">{{ titleText }}</div>
        <div class="card-filename" v-if="data.filename">📄 {{ data.filename }}</div>
      </div>
    </div>

    <!-- 替换统计 -->
    <div class="search-count" v-if="data.count !== undefined">
      <span :class="['count-badge', data.count === 0 ? 'zero' : 'found']">
        {{ data.count }}
      </span>
      <span class="count-label">
        {{ data.action === 'search_replace' ? '处替换' : '处匹配' }}
      </span>
    </div>

    <!-- 替换详情 -->
    <div class="search-detail" v-if="data.find_text">
      <div class="detail-line">
        <span class="dl-label">查找</span>
        <span class="dl-val find">「{{ data.find_text }}」</span>
      </div>
      <div class="detail-line" v-if="data.replace_text">
        <span class="dl-label">替换为</span>
        <span class="dl-val replace">「{{ data.replace_text }}」</span>
      </div>
    </div>

    <!-- 搜索结果 -->
    <div class="results-list" v-if="data.results?.length">
      <div class="result-row" v-for="(r, i) in data.results.slice(0, 8)" :key="i">
        <span class="result-idx">#{{ i + 1 }}</span>
        <span class="result-text">{{ truncate(r.text || r.content || r.snippet || '', 80) }}</span>
      </div>
      <div class="result-more" v-if="data.results.length > 8">
        … 还有 {{ data.results.length - 8 }} 条结果
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ data: Record<string, any> }>()

const titleText = computed(() => {
  return props.data.action === 'find_text' ? '搜索文本' : '查找替换'
})

function truncate(s: string, n: number): string {
  return s && s.length > n ? s.slice(0, n) + '...' : s || ''
}
</script>

<style scoped>
.word-card { padding: 12px 4px; }
.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.search-icon { font-size: 20px; }
.card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}
.card-filename {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}
.search-count {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.count-badge {
  padding: 2px 12px;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 700;
}
.count-badge.found { background: #dbeafe; color: #2563eb; }
.count-badge.zero { background: var(--bg-secondary); color: var(--text-secondary); }
.count-label { font-size: 13px; color: var(--text-secondary); }
.search-detail {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 12px;
  margin-bottom: 8px;
}
.detail-line {
  display: flex;
  gap: 8px;
  font-size: 13px;
  padding: 2px 0;
  align-items: baseline;
}
.dl-label { color: var(--text-secondary); min-width: 4em; }
.dl-val { word-break: break-all; }
.dl-val.find { color: #dc2626; }
.dl-val.replace { color: #16a34a; }
.results-list {
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
}
.result-row {
  display: flex;
  gap: 8px;
  padding: 5px 10px;
  font-size: 12px;
  border-bottom: 1px solid var(--border);
}
.result-row:last-child { border-bottom: none; }
.result-idx { color: var(--text-secondary); flex-shrink: 0; }
.result-text { color: var(--text-primary); word-break: break-word; }
.result-more {
  padding: 6px;
  font-size: 11px;
  color: var(--text-secondary);
  text-align: center;
  background: var(--bg-secondary);
}
</style>
