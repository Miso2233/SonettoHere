import { storeToRefs } from 'pinia'
import { useSessionStore } from '@/stores/sessionStore'
import type { SessionInfo } from '@/types'

/**
 * Composable 封装 — 委托到 Pinia store。
 * 使用 storeToRefs 保持响应式解构（Pinia 会 auto-unwrap refs，storeToRefs 恢复 ref 包装）。
 */
export function useSession() {
  const store = useSessionStore()
  store.initIfNeeded()

  const { sessionId, sessions } = storeToRefs(store)

  return {
    sessionId,
    sessions,
    createSession: store.createSession,
    switchSession: store.switchSession,
    deleteSession: store.deleteSession,
    refreshSessions: store.refreshSessions,
  }
}

// 模块级函数导出（向后兼容）
export const refreshSessions = () => useSessionStore().refreshSessions()
export const switchSession = (id: string) => useSessionStore().switchSession(id)
