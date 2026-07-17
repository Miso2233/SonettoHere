import { storeToRefs } from 'pinia'
import { useSidebarStore } from '@/stores/sidebarStore'

/**
 * Composable 封装 — 委托到 Pinia store。
 * 使用 storeToRefs 保持响应式绑定（Pinia 会 auto-unwrap refs）。
 */
export function useSidebar() {
  const store = useSidebarStore()
  const { effectiveCollapsed, userCollapsed } = storeToRefs(store)

  return {
    effectiveCollapsed,
    userCollapsed,
    toggleSidebar: store.toggleSidebar,
    setUserCollapsed: store.setUserCollapsed,
  }
}
