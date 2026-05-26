import { ref, onUnmounted } from 'vue'
import { api } from '@/api'
import type { HealthResponse } from '@/types'

export const health = ref<HealthResponse | null>(null)
let _timer: ReturnType<typeof setInterval> | null = null

export async function refreshHealth() {
  try {
    health.value = await api.health()
  } catch {
    health.value = null
  }
}

export function startPolling(intervalMs = 30000) {
  stopPolling()
  refreshHealth()
  _timer = setInterval(refreshHealth, intervalMs)
}

export function stopPolling() {
  if (_timer !== null) {
    clearInterval(_timer)
    _timer = null
  }
}

export function useHealth() {
  onUnmounted(stopPolling)
  return { health, refreshHealth, startPolling, stopPolling }
}
