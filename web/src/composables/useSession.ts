import { ref } from 'vue'
import { api } from '@/api'
import { removeTurnsFromStorage, disconnectSession, TURNS_KEY_PREFIX } from '@/composables/useChat'
import type { SessionInfo } from '@/types'

const STORAGE_KEY = 'sonetto_session_id'

// Module-level shared state — all callers share the same session
const sessionId = ref('')
const sessions = ref<SessionInfo[]>([])
let _initialized = false

async function initIfNeeded() {
  if (_initialized) {
    console.log('[useSession:init] 已初始化, 跳过')
    return
  }
  _initialized = true

  const stored = localStorage.getItem(STORAGE_KEY)
  console.log(`[useSession:init] 从 localStorage 读取 stored="${stored}"`)
  if (stored) {
    try {
      await api.getSession(stored)
      sessionId.value = stored
      console.log(`[useSession:init] 恢复已有会话: "${stored}"`)
    } catch (e) {
      console.warn(`[useSession:init] 会话 "${stored}" 不存在于后端, 创建新会话:`, e)
      await _createSession()
    }
  } else {
    console.log('[useSession:init] localStorage 中无会话记录, 创建新会话')
    await _createSession()
  }
  await refreshSessions()
  cleanupOrphanedCaches()
  console.log(`[useSession:init] 完成, sessionId="${sessionId.value}", 共 ${sessions.value.length} 个会话`)
}

export async function refreshSessions() {
  try {
    const res = await api.listSessions()
    sessions.value = res.sessions
    console.log(`[useSession:refresh] 获取到 ${res.sessions.length} 个会话`)
  } catch (e) {
    console.warn('[useSession:refresh] 获取会话列表失败:', e)
    sessions.value = []
  }
}

async function _createSession() {
  const res = await api.createSession()
  sessionId.value = res.session_id
  localStorage.setItem(STORAGE_KEY, res.session_id)
  console.log(`[useSession:create] 创建新会话: "${res.session_id}"`)
}

async function createSession() {
  console.log('[useSession] createSession() 被调用')
  await _createSession()
  await refreshSessions()
}

export async function switchSession(id: string) {
  console.log(`[useSession] switchSession("${id}") 被调用`)
  sessionId.value = id
  localStorage.setItem(STORAGE_KEY, id)
}

async function deleteSession(id: string) {
  console.log(`[useSession] deleteSession("${id}") 被调用`)
  await api.deleteSession(id)
  disconnectSession(id)
  removeTurnsFromStorage(id)
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
      console.log(`[useSession:cleanup] 删除孤儿缓存 会话=${sid}, key=${key}`)
    }
  }
  if (removed > 0) {
    console.log(`[useSession:cleanup] 共清理 ${removed} 个孤儿缓存, 释放约 ${(totalSize * 2 / 1024).toFixed(1)} KB`)
  } else {
    console.log('[useSession:cleanup] 无孤儿缓存需清理')
  }
}
