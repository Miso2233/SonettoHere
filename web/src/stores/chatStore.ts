import { reactive, computed, type Ref } from 'vue'
import { defineStore } from 'pinia'
import type {
  ServerEvent, ChatTurn, ToolCall, ThinkingBlock,
  TurnEvent, ContextUsage, AskUserEvent, MemoryToolEvent,
  ClientMessage, TokenEvent,
} from '@/types'
import { buildFlatMessage, buildTimestamp, parseReferences } from '@/utils/references'
import type { ParsedRef } from '@/utils/references'
import { getToken } from '@/api'
import { memoryHandlers, type MemoryEventType } from '@/composables/useChat.memory'
import { turnHandlers } from '@/composables/useChat.handlers'

const TIME_SUFFIX_RE = /（\d{4}-\d{2}-\d{2} \w{3} \d{2}:\d{2}）$/
export const TURNS_KEY_PREFIX = 'sonetto_turns_'
const SID_RE = /^[0-9a-f]{32}$/i

function isValidSessionId(sid: string): boolean {
  return SID_RE.test(sid)
}

function migrateLegacyTurn(turn: any): ChatTurn {
  if (Array.isArray(turn.refs)) {
    return { memoryEvents: [], ...turn } as ChatTurn
  }
  const prevMsg = (turn.userMessage ?? '') as string
  const { cleanText, refs } = parseReferences(prevMsg || '')
  const text = refs.length > 0 ? cleanText : prevMsg.replace(TIME_SUFFIX_RE, '')
  return { ...turn, userMessage: text, refs, memoryEvents: [] }
}

function loadAllTurnsFromStorage(): Map<string, ChatTurn[]> {
  const map = new Map<string, ChatTurn[]>()
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (key && key.startsWith(TURNS_KEY_PREFIX)) {
      const sid = key.slice(TURNS_KEY_PREFIX.length)
      try {
        const raw = localStorage.getItem(key) || '[]'
        const data = JSON.parse(raw)
        if (Array.isArray(data)) {
          map.set(sid, data.map(migrateLegacyTurn))
        }
      } catch { /* skip corrupt entry */ }
    }
  }
  return map
}

// ── 会话通道接口 ──

export interface SessionChannel {
  ws: WebSocket | null
  connected: boolean
  isStreaming: boolean
  isAwaitingUser: boolean
  turns: ChatTurn[]
  currentTurn: ChatTurn | null
  error: string | null
  contextUsage: ContextUsage | null
  taskTrackerData: Record<string, unknown> | null
  reconnectTimer: ReturnType<typeof setTimeout> | null
  initialized: boolean
  _awaitingToolName: string | null
  parentSessionId: string | null
  privateMode: boolean
  autoApprove: boolean
}

export const useChatStore = defineStore('chat', () => {
  const channels = reactive(new Map<string, SessionChannel>())
  const turnsCache = loadAllTurnsFromStorage()

  // ── 计算属性 ──

  const allSessionStatuses = computed(() => {
    const map: Record<string, { connected: boolean; isStreaming: boolean; isAwaitingUser: boolean }> = {}
    for (const [sid, ch] of channels) {
      map[sid] = { connected: ch.connected, isStreaming: ch.isStreaming, isAwaitingUser: ch.isAwaitingUser }
    }
    return map
  })

  // ── 通道管理 ──

  function getOrCreateChannel(sid: string): SessionChannel {
    if (!channels.has(sid)) {
      const cached = turnsCache.get(sid)
      channels.set(sid, {
        ws: null,
        connected: false,
        isStreaming: false,
        isAwaitingUser: false,
        turns: cached ? [...cached] : [],
        currentTurn: null,
        error: null,
        contextUsage: null,
        taskTrackerData: null,
        reconnectTimer: null,
        initialized: false,
        _awaitingToolName: null,
        parentSessionId: null,
        privateMode: false,
        autoApprove: false,
      })
    }
    return channels.get(sid)!
  }

  function saveTurnsToStorage(sid: string, data: ChatTurn[]) {
    const key = TURNS_KEY_PREFIX + sid
    try {
      localStorage.setItem(key, JSON.stringify(data))
    } catch { /* quota exceeded */ }
  }

  function persistTurns(sid: string) {
    const ch = channels.get(sid)
    if (!ch) return
    const snapshot = [...ch.turns]
    turnsCache.set(sid, snapshot)
    saveTurnsToStorage(sid, snapshot)
  }

  function removeTurnsFromStorage(sid: string) {
    localStorage.removeItem(TURNS_KEY_PREFIX + sid)
  }

  // ── WebSocket 生命周期 ──

  function connectSession(sid: string) {
    if (!isValidSessionId(sid)) return
    const ch = getOrCreateChannel(sid)
    if (ch.ws?.readyState === WebSocket.OPEN) return

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const token = getToken()
    ch.ws = new WebSocket(`${protocol}//${location.host}/ws/chat/${sid}`, [token])

    ch.ws.onopen = () => {
      ch.connected = true
      if (ch.reconnectTimer) {
        clearTimeout(ch.reconnectTimer)
        ch.reconnectTimer = null
      }
    }

    ch.ws.onclose = () => {
      ch.connected = false
      ch.reconnectTimer = setTimeout(() => connectSession(sid), 3000)
    }

    ch.ws.onmessage = (event) => {
      try {
        const msg: ServerEvent = JSON.parse(event.data)
        handleEventForChannel(sid, msg)
      } catch (e) {
        console.error('[chatStore] WS message error:', e)
      }
    }
  }

  function ensureConnected(sid: string) {
    if (!sid || !isValidSessionId(sid)) return
    const ch = getOrCreateChannel(sid)
    if (ch.initialized) return
    ch.initialized = true
    connectSession(sid)
  }

  function disconnectChannel(sid: string) {
    const ch = channels.get(sid)
    if (!ch) return
    if (ch.reconnectTimer) {
      clearTimeout(ch.reconnectTimer)
      ch.reconnectTimer = null
    }
    if (ch.ws) {
      ch.ws.onclose = null
      ch.ws.close()
      ch.ws = null
    }
    ch.connected = false
    ch.initialized = false
    channels.delete(sid)
  }

  // ── 事件路由 ──

  function handleEventForChannel(sid: string, event: ServerEvent) {
    const ch = channels.get(sid)
    if (!ch) return

    if (event.type === 'context_usage') {
      ch.contextUsage = event.payload
      return
    }

    if (event.type === 'sub_session_created') {
      void handleSubSessionCreated(sid, event)
      return
    }

    const memoryHandler = memoryHandlers.get(event.type as MemoryEventType)
    if (typeof memoryHandler === 'function') {
      memoryHandler(ch, sid, event)
      return
    }

    const turn = ch.currentTurn
    if (!turn) return

    const turnHandler = turnHandlers.get(event.type)
    if (typeof turnHandler === 'function') {
      turnHandler(ch, sid, turn, event)
    }
  }

  /** sub_session_created 的异步处理器（需通过 import() 获取 sessionStore 避免循环依赖）。 */
  async function handleSubSessionCreated(sid: string, event: ServerEvent & { type: 'sub_session_created' }) {
    const { useSessionStore } = await import('@/stores/sessionStore')
    const sessionStore = useSessionStore()
    const subId = event.payload.sub_session_id
    sessionStore.refreshSessions()
    ensureConnected(subId)

    const subCh = getOrCreateChannel(subId)
    subCh.parentSessionId = event.payload.parent_session_id
    subCh.isStreaming = true
    subCh.currentTurn = {
      id: crypto.randomUUID(),
      userMessage: event.payload.task || '(子 Agent 任务)',
      refs: [],
      events: [],
      memoryEvents: [],
      finalAnswer: null,
    }
    sessionStore.switchSession(subId)
  }

  // ── 发送消息 ──

  function send(
    sid: string,
    text: string,
    refs: ParsedRef[] = [],
    providerId?: string,
    modelName?: string,
    imageRecognition?: boolean,
    imagePaths?: string[],
  ) {
    const ch = channels.get(sid)
    if (!ch?.ws || ch.ws.readyState !== WebSocket.OPEN) return
    ch.isStreaming = true
    ch.error = null

    const timestamp = buildTimestamp()
    const flatMsg = buildFlatMessage(text, timestamp, refs)

    ch.currentTurn = {
      id: crypto.randomUUID(),
      userMessage: text,
      refs,
      imageRefs: imageRecognition && imagePaths?.length
        ? imagePaths.map(p => ({ type: 'file' as const, path: p, label: p.split(/[/\\]/).pop() || p }))
        : undefined,
      events: [],
      memoryEvents: [],
      finalAnswer: null,
    }

    const payload: ClientMessage = {
      type: 'chat',
      payload: {
        message: flatMsg,
        private: ch.privateMode,
        auto_approve: ch.autoApprove,
        provider_id: providerId,
        model_name: modelName,
        ...(imageRecognition && imagePaths?.length ? { image_recognition: true, image_refs: imagePaths } : {}),
      },
    }
    ch.ws.send(JSON.stringify(payload))
  }

  function cancel(sid: string) {
    const ch = channels.get(sid)
    if (!ch?.ws || ch.ws.readyState !== WebSocket.OPEN) return
    ch.ws.send(JSON.stringify({ type: 'cancel', payload: {} } as ClientMessage))
  }

  function sendUserResponse(sid: string, interactionId: string, response: string | string[]) {
    const ch = channels.get(sid)
    if (!ch?.ws || ch.ws.readyState !== WebSocket.OPEN) return
    const turn = ch.currentTurn
    if (turn) {
      for (const ev of turn.events) {
        if (ev.kind === 'tool' && ev.interaction?.interactionId === interactionId) {
          ev.interaction.submitted = true
          break
        }
      }
    }
    ch.ws.send(JSON.stringify({
      type: 'user_response',
      payload: { interaction_id: interactionId, response },
    } as ClientMessage))
  }

  function removeTurns(sid: string, count: number) {
    const ch = channels.get(sid)
    if (!ch || ch.turns.length === 0) return
    const actual = Math.min(count, ch.turns.length)
    ch.turns.splice(ch.turns.length - actual, actual)
    if (!ch.privateMode) {
      persistTurns(sid)
    }
  }

  function updateAutoApprove(sid: string, val: boolean) {
    const ch = channels.get(sid)
    if (!ch) return
    ch.autoApprove = val
    if (ch.ws?.readyState === WebSocket.OPEN) {
      ch.ws.send(JSON.stringify({
        type: 'update_auto_approve',
        payload: { auto_approve: val },
      } as ClientMessage))
    }
  }

  return {
    channels,
    allSessionStatuses,
    getOrCreateChannel,
    persistTurns,
    removeTurnsFromStorage,
    ensureConnected,
    disconnectChannel,
    connectSession,
    handleEventForChannel,
    send,
    cancel,
    sendUserResponse,
    removeTurns,
    updateAutoApprove,
  }
})

// ══════════════════════════════════════════════════
// 以下为纯工具函数（不依赖 store 实例，可直接导入使用）
// ══════════════════════════════════════════════════

export function findLastThinking(events: TurnEvent[]): ThinkingBlock | undefined {
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i].kind === 'thinking') {
      return events[i] as ThinkingBlock
    }
  }
  return undefined
}

export function findToolByCallId(events: TurnEvent[], callId: string): ToolCall | undefined {
  for (const e of events) {
    if (e.kind === 'tool' && e.callId === callId) {
      return e as ToolCall
    }
  }
  return undefined
}

export function findFirstRunningToolForInteraction(events: TurnEvent[], toolName: string): ToolCall | undefined {
  for (let i = 0; i < events.length; i++) {
    const e = events[i]
    if (e.kind === 'tool' && e.name === toolName && e.status === 'running' && !e.interaction) {
      return e as ToolCall
    }
  }
  return undefined
}

export function findBestMatchingTool(events: TurnEvent[], toolName: string): ToolCall | undefined {
  for (let i = 0; i < events.length; i++) {
    const e = events[i]
    if (e.kind === 'tool' && e.name === toolName && e.status === 'running' && e.interaction?.submitted) {
      return e as ToolCall
    }
  }
  for (let i = 0; i < events.length; i++) {
    const e = events[i]
    if (e.kind === 'tool' && e.name === toolName && e.status === 'running' && e.interaction) {
      return e as ToolCall
    }
  }
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i]
    if (e.kind === 'tool' && e.name === toolName && e.status === 'running') {
      return e as ToolCall
    }
  }
  return undefined
}

export function findTurnByBackendId(ch: SessionChannel, turnId: string): ChatTurn | undefined {
  if (ch.currentTurn?.turnId === turnId) return ch.currentTurn
  return ch.turns.find(t => t.turnId === turnId)
}

export function findRunningMemoryTool(events: MemoryToolEvent[], toolName: string): MemoryToolEvent | undefined {
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i]
    if (e.name === toolName && e.status === 'running') return e
  }
  return undefined
}
