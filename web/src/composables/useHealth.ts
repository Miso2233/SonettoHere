import { computed, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useHealthStore } from '@/stores/healthStore'
import type { HealthResponse } from '@/types'

// 模块级导出（向后兼容）
function getStore() {
  return useHealthStore()
}

/** @deprecated 直接使用 useHealthStore() */
export const health = computed<HealthResponse | null>(() => getStore().health)
export const refreshHealth = () => getStore().refresh()
export const startPolling = (ms?: number) => getStore().startPolling(ms)
export const stopPolling = () => getStore().stopPolling()

/**
 * Composable 封装 — 委托到 Pinia store。
 * 使用 storeToRefs 保持响应式绑定。
 */
export function useHealth() {
  const store = getStore()
  const { health } = storeToRefs(store)

  onUnmounted(() => store.stopPolling())

  return {
    health,
    refreshHealth: store.refresh,
    startPolling: store.startPolling,
    stopPolling: store.stopPolling,
  }
}
