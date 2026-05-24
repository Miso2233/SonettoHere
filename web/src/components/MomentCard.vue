<template>
  <div class="moment-card">
    <div class="moment-header">
      <span class="moment-title">💭 随机记忆</span>
      <span v-if="moment" class="moment-theme">{{ moment.theme }}</span>
      <button class="btn-shuffle" @click="fetchMoment" :disabled="loading">
        换一个
      </button>
    </div>
    <div class="moment-body">
      <div v-if="loading" class="moment-loading">
        <span class="spinner"></span>
      </div>
      <template v-else-if="moment">
        <div class="moment-current">{{ moment.description }}</div>
        <div v-if="moment.history.length > 1" class="moment-history">
          <div class="moment-timeline">
            <div
              v-for="(h, i) in moment.history.slice(1)"
              :key="i"
              class="moment-history-item"
            >
              <div class="timeline-dot"></div>
              <div class="timeline-content">
                <div class="history-desc">{{ h.description }}</div>
                <div class="history-time">{{ h.time }}</div>
              </div>
            </div>
          </div>
        </div>
      </template>
      <div v-else class="moment-empty">
        暂无记忆条目
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { api } from '@/api'
import type { MomentItem } from '@/types'

const moment = ref<MomentItem | null>(null)
const loading = ref(false)

async function fetchMoment() {
  console.log('[MomentCard] fetchMoment called')
  loading.value = true
  try {
    const res = await api.getMoment()
    console.log('[MomentCard] API response:', res)
    moment.value = res.moment
  } catch (e) {
    console.error('[MomentCard] API error:', e)
    moment.value = null
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  console.log('[MomentCard] mounted')
  fetchMoment()
})
</script>

<style scoped>
.moment-card {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--bg-card);
  box-shadow: var(--shadow);
  overflow: hidden;
  margin-bottom: 16px;
}

.moment-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border);
}

.moment-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.moment-theme {
  font-size: 11px;
  font-weight: 600;
  color: var(--accent);
  background: var(--user-bubble);
  padding: 2px 8px;
  border-radius: 4px;
  margin-right: auto;
}

.btn-shuffle {
  padding: 4px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  font-family: inherit;
  transition: background 0.15s;
}

.btn-shuffle:hover:not(:disabled) {
  background: var(--bg-secondary);
}

.moment-body {
  padding: 16px;
}

.moment-current {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
  padding: 8px 12px;
  background: var(--bg-secondary);
  border-radius: 8px;
  border-left: 3px solid var(--accent);
}

.moment-history {
  margin-top: 16px;
}

.moment-timeline {
  position: relative;
  padding-left: 20px;
}

.moment-timeline::before {
  content: '';
  position: absolute;
  left: 5px;
  top: 4px;
  bottom: 4px;
  width: 1px;
  background: var(--border);
}

.moment-history-item {
  display: flex;
  gap: 10px;
  padding: 6px 0;
}

.timeline-dot {
  flex-shrink: 0;
  width: 11px;
  height: 11px;
  border-radius: 50%;
  background: var(--bg-card);
  border: 2px solid var(--accent-light);
  margin-left: -20px;
  margin-top: 4px;
}

.timeline-content {
  flex: 1;
  min-width: 0;
}

.history-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.history-time {
  font-size: 11px;
  color: var(--text-secondary);
  opacity: 0.6;
  margin-top: 2px;
}

.moment-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px 0;
}

.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.moment-empty {
  text-align: center;
  color: var(--text-secondary);
  font-size: 13px;
  padding: 24px 0;
}
</style>
