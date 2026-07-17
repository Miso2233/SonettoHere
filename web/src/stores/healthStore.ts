import { ref, onUnmounted } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api'
import type { HealthResponse } from '@/types'

export const useHealthStore = defineStore('health', () => {
  const health = ref<HealthResponse | null>(null)
  let _timer: ReturnType<typeof setInterval> | null = null

  async function refresh() {
    try {
      health.value = await api.health()
    } catch {
      health.value = null
    }
  }

  function startPolling(intervalMs = 30000) {
    stopPolling()
    refresh()
    _timer = setInterval(refresh, intervalMs)
  }

  function stopPolling() {
    if (_timer !== null) {
      clearInterval(_timer)
      _timer = null
    }
  }

  return { health, refresh, startPolling, stopPolling }
})
