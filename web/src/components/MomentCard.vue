<template>
  <div class="moment-card">
    <div class="moment-header">
      <span class="moment-title">💭 随机记忆</span>
      <span v-if="moment" class="moment-theme">{{ moment.theme_label ?? moment.theme }}</span>
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
