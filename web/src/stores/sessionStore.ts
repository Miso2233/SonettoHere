import { ref } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api'
import type { SessionInfo } from '@/types'
import { useChatStore } from './chatStore'

const STORAGE_KEY = 'sonetto_session_id'
const TURNS_KEY_PREFIX = 'sonetto_turns_'

export const useSessionStore = defineStore('session', () => {
  const sessionId = ref('')
  const sessions = ref<SessionInfo[]>([])
  let _initialized = false

  async function initIfNeeded() {
    if (_initialized) return
    _initialized = true

    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      try {
        await api.getSession(stored)
        sessionId.value = stored
      } catch {
        await _createSession()
      }
    } else {
      await _createSession()
    }
    await refreshSessions()
    cleanupOrphanedCaches()
  }

  async function refreshSessions() {
    try {
      const res = await api.listSessions()
      sessions.value = res.sessions
    } catch {
      sessions.value = []
    }
  }

  async function _createSession() {
    const res = await api.createSession()
    sessionId.value = res.session_id
    localStorage.setItem(STORAGE_KEY, res.session_id)
  }

  async function createSession() {
    await _createSession()
    await refreshSessions()
  }

  async function switchSession(id: string) {
    sessionId.value = id
    localStorage.setItem(STORAGE_KEY, id)
  }

  async function deleteSession(id: string) {
    await api.deleteSession(id)
    // 断开 WS 并清理缓存（通过 chatStore）
    const chatStore = useChatStore()
    chatStore.disconnectChannel(id)
    localStorage.removeItem(TURNS_KEY_PREFIX + id)
    if (sessionId.value === id) {
      await refreshSessions()
      if (sessions.value.length > 0) {
        await switchSession(sessions.value[0].session_id)
      } else {
        await createSession()
      }
    } else {
      await refreshSessions()
    }
  }

  async function constifySession(id: string, name: string) {
    await api.constifySession(id, name)
    await refreshSessions()
  }

  async function unconstifySession(id: string) {
    await api.unconstifySession(id)
    await refreshSessions()
  }

  async function generateSessionTitle(id: string): Promise<string> {
    const res = await api.generateSessionTitle(id)
    return res.title
  }

  /** 清理后端已不存在的会话的 localStorage 孤儿缓存 */
  function cleanupOrphanedCaches() {
    const validIds = new Set(sessions.value.map(s => s.session_id))
    let removed = 0
    let totalSize = 0
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key && key.startsWith(TURNS_KEY_PREFIX)) {
        const sid = key.slice(TURNS_KEY_PREFIX.length)
        if (!sid || validIds.has(sid)) continue
        const raw = localStorage.getItem(key)
        localStorage.removeItem(key)
        removed++
        totalSize += (raw ? raw.length : 0) + key.length
      }
    }
  }

  return {
    sessionId,
    sessions,
    initIfNeeded,
    refreshSessions,
    createSession,
    switchSession,
    deleteSession,
    constifySession,
    unconstifySession,
    generateSessionTitle,
  }
})
