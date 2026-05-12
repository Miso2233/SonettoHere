import { ref } from 'vue'
import { api } from '@/api'
import type { SessionInfo } from '@/types'

const STORAGE_KEY = 'sonetto_session_id'

// Module-level shared state — all callers share the same session
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

export function useSession() {
  initIfNeeded()
  return { sessionId, sessions, createSession, switchSession, deleteSession, refreshSessions }
}
