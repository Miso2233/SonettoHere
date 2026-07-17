import { ref, computed, watch } from 'vue'
import { defineStore } from 'pinia'

const STORAGE_KEY = 'sonetto_sidebar_collapsed'

export const useSidebarStore = defineStore('sidebar', () => {
  // ── 从 localStorage 恢复用户偏好 ──
  const userCollapsed = ref(false)
  const forcedCollapsed = ref(false)

  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved !== null) userCollapsed.value = saved === 'true'
  } catch { /* localStorage 不可用 */ }

  // matchMedia 监听窄屏自动折叠
  const mql = window.matchMedia('(max-width: 900px)')
  forcedCollapsed.value = mql.matches

  function onMqlChange(e: MediaQueryListEvent) {
    forcedCollapsed.value = e.matches
  }
  mql.addEventListener('change', onMqlChange)

  // 持久化用户偏好
  watch(userCollapsed, (v) => {
    try { localStorage.setItem(STORAGE_KEY, String(v)) } catch { /* noop */ }
  })

  const effectiveCollapsed = computed(() => userCollapsed.value || forcedCollapsed.value)

  function toggleSidebar() {
    userCollapsed.value = !userCollapsed.value
  }

  function setUserCollapsed(v: boolean) {
    userCollapsed.value = v
  }

  return {
    userCollapsed,
    forcedCollapsed,
    effectiveCollapsed,
    toggleSidebar,
    setUserCollapsed,
  }
})
