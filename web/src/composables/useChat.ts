import { reactive, computed, watch, nextTick, type Ref } from 'vue'
import type { ClientMessage, ServerEvent, ChatTurn, ToolCall, ThinkingBlock, TurnEvent, ContextUsage, AskUserEvent } from '@/types'
import { refreshSessions } from '@/composables/useSession'

const TURNS_KEY_PREFIX = 'sonetto_turns_'

// 从 localStorage 恢复所有会话的消息缓存（页面刷新后仍保留）
function loadAllTurnsFromStorage(): Map<string, ChatTurn[]> {
  const map = new Map<string, ChatTurn[]>()
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (key && key.startsWith(TURNS_KEY_PREFIX)) {
      const sid = key.slice(TURNS_KEY_PREFIX.length)
      try {
        const data = JSON.parse(localStorage.getItem(key) || '[]')
        if (Array.isArray(data)) {
          map.set(sid, data)
        }
      } catch { /* 忽略解析错误 */ }
    }
  }
  return map
}

function saveTurnsToStorage(sid: string, data: ChatTurn[]) {
  try {
    localStorage.setItem(TURNS_KEY_PREFIX + sid, JSON.stringify(data))
  } catch { /* storage 满时静默失败 */ }
}

export function removeTurnsFromStorage(sid: string) {
  localStorage.removeItem(TURNS_KEY_PREFIX + sid)
}

export function disconnectSession(sid: string) {
  const ch = channels.get(sid)
  if (!ch) return
  if (ch.reconnectTimer) {
    clearTimeout(ch.reconnectTimer)
    ch.reconnectTimer = null
  }
  ch.ws?.close()
  ch.ws = null
  ch.connected = false
  ch.initialized = false
  channels.delete(sid)
}

const turnsCache = loadAllTurnsFromStorage()

// ── 多会话通道 ─────────────────────────────────────────────

interface SessionChannel {
  ws: WebSocket | null
  connected: boolean
  isStreaming: boolean
  turns: ChatTurn[]
  currentTurn: ChatTurn | null
  error: string | null
  contextUsage: ContextUsage | null
  reconnectTimer: ReturnType<typeof setTimeout> | null
  initialized: boolean
}

const channels = reactive(new Map<string, SessionChannel>())

// 所有 Session 的连接/流式状态（模块级，供 sidebar 使用）
export const allSessionStatuses = computed(() => {
  const map: Record<string, { connected: boolean; isStreaming: boolean }> = {}
  for (const [sid, ch] of channels) {
    map[sid] = { connected: ch.connected, isStreaming: ch.isStreaming }
  }
  return map
})

function getOrCreateChannel(sid: string): SessionChannel {
  if (!channels.has(sid)) {
    channels.set(sid, {
      ws: null,
      connected: false,
      isStreaming: false,
      turns: [] as ChatTurn[],
      currentTurn: null,
      error: null,
      contextUsage: null,
      reconnectTimer: null,
      initialized: false,
    })
  }
  return channels.get(sid)!
}

function persistTurns(sid: string) {
  const ch = channels.get(sid)
  if (!ch) return
  const snapshot = [...ch.turns]
  turnsCache.set(sid, snapshot)
  saveTurnsToStorage(sid, snapshot)
}

// ── WebSocket 生命周期（每 Session 独立管理） ──────────────

function connectSession(sid: string) {
  const ch = getOrCreateChannel(sid)
  if (ch.ws?.readyState === WebSocket.OPEN) return

  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${protocol}//${location.host}/ws/chat/${sid}`
  ch.ws = new WebSocket(url)

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
      console.log('[useChat] WS event received:', msg.type, 'session:', sid, msg.type === 'ask_user' ? {
        tool_name: (msg as AskUserEvent).payload.tool_name,
        interaction_id: (msg as AskUserEvent).payload.interaction_id,
      } : '')
      handleEventForChannel(sid, msg)
    } catch (e) {
      console.error('[useChat] WS message parse/handle error:', e)
    }
  }
}

function ensureConnected(sid: string) {
  if (!sid) return
  const ch = getOrCreateChannel(sid)
  if (ch.initialized) return
  ch.initialized = true
  connectSession(sid)
}

// ── 事件路由 ──────────────────────────────────────────────

function handleEventForChannel(sid: string, event: ServerEvent) {
  const ch = channels.get(sid)
  if (!ch) return

  // context_usage 可以在无活跃轮次时接收（如连接初始化）
  if (event.type === 'context_usage') {
    ch.contextUsage = event.payload
    return
  }

  const turn = ch.currentTurn
  if (!turn) return

  switch (event.type) {
    case 'thinking_start':
      turn.events.push({ kind: 'thinking', tokens: '', done: false, becameAnswer: false })
      break

    case 'token': {
      const lastThink = findLastThinking(turn.events)
      if (lastThink) {
        lastThink.tokens += event.payload.token
      }
      break
    }

    case 'thinking_end': {
      const lastThink = findLastThinking(turn.events)
      if (lastThink) {
        lastThink.done = true
      }
      break
    }

    case 'tool_start': {
      console.log(`[useChat] tool_start: "${event.payload.tool_name}"`, { input: event.payload.input, session: sid })
      turn.events.push({
        kind: 'tool',
        name: event.payload.tool_name,
        input: event.payload.input,
        output: null,
        elapsed: null,
        status: 'running',
      })
      break
    }

    case 'tool_end': {
      const tc = findRunningTool(turn.events, event.payload.tool_name)
      if (tc) {
        tc.output = event.payload.output
        tc.elapsed = event.payload.elapsed
        tc.status = 'done'
        if (event.payload.tool_data) {
          tc.toolData = event.payload.tool_data
        }
        console.log(`[useChat] tool_end: "${event.payload.tool_name}"`, {
          output_len: (event.payload.output || '').length,
          output_preview: (event.payload.output || '').slice(0, 100),
          has_tool_data: !!event.payload.tool_data,
          elapsed: event.payload.elapsed,
          session: sid,
        })
      }
      break
    }

    case 'tool_error': {
      const tc = findRunningTool(turn.events, event.payload.tool_name)
      if (tc) {
        tc.status = 'error'
      }
      break
    }

    case 'answer': {
      const lastThink = findLastThinking(turn.events)
      if (lastThink) {
        lastThink.becameAnswer = true
      }
      turn.finalAnswer = event.payload.content
      break
    }

    case 'done':
      if (event.payload.context_usage) {
        ch.contextUsage = event.payload.context_usage
      }
      if (ch.currentTurn) {
        const lastThink = findLastThinking(ch.currentTurn.events)
        if (lastThink?.becameAnswer) {
          const turnToFinalize = ch.currentTurn
          void nextTick(() => {
            setTimeout(() => {
              ch.turns.push(turnToFinalize)
              ch.currentTurn = null
              ch.isStreaming = false
              persistTurns(sid)
            }, 420)
          })
        } else {
          ch.turns.push(ch.currentTurn)
          ch.currentTurn = null
          ch.isStreaming = false
          persistTurns(sid)
        }
        void refreshSessions()  // 轮次结束，刷新会话列表以更新 message_count
      } else {
        ch.isStreaming = false
      }
      break

    case 'error':
      ch.error = event.payload.message
      ch.isStreaming = false
      break

    case 'pong':
      break

    case 'ask_user': {
      const ae = event as AskUserEvent
      console.log('[useChat] received ask_user event:', {
        tool_name: ae.payload.tool_name,
        question: ae.payload.question?.slice(0, 50),
        mode: ae.payload.mode,
        interaction_id: ae.payload.interaction_id,
        session: sid,
      })
      const runningTool = findRunningTool(turn.events, ae.payload.tool_name)
      console.log('[useChat] findRunningTool result:', runningTool ? {
        name: runningTool.name,
        status: runningTool.status,
        has_interaction: !!runningTool.interaction,
      } : 'NOT FOUND')
      if (runningTool) {
        runningTool.interaction = {
          question: ae.payload.question,
          mode: ae.payload.mode,
          options: ae.payload.options,
          interactionId: ae.payload.interaction_id,
          submitted: false,
        }
      }
      break
    }
  }
}

// ── useChat composable ─────────────────────────────────────

export function useChat(sessionId: Ref<string>) {
  const activeChannel = computed(() => getOrCreateChannel(sessionId.value))

  // 暴露给 ChatView 的响应式属性（指向当前 Session 通道）
  const connected = computed(() => activeChannel.value.connected)
  const isStreaming = computed(() => activeChannel.value.isStreaming)
  const turns = computed(() => activeChannel.value.turns)
  const currentTurn = computed(() => activeChannel.value.currentTurn)
  const error = computed(() => activeChannel.value.error)
  const contextUsage = computed(() => activeChannel.value.contextUsage)

  // Session 切换：只确保新 Session 的 WS 连接，不断开旧的
  watch(
    sessionId,
    (newId, oldId) => {
      if (oldId) persistTurns(oldId)
      ensureConnected(newId)
      // 恢复新会话的消息缓存（页面刷新场景）
      const cached = turnsCache.get(newId)
      const ch = getOrCreateChannel(newId)
      if (cached && ch.turns.length === 0) {
        ch.turns.push(...cached)
      }
    },
    { immediate: true }
  )

  function send(message: string) {
    const ch = activeChannel.value
    if (!ch.ws || ch.ws.readyState !== WebSocket.OPEN) return
    ch.isStreaming = true
    ch.error = null

    const turn: ChatTurn = {
      id: crypto.randomUUID(),
      userMessage: message,
      events: [],
      finalAnswer: null,
    }
    ch.currentTurn = turn

    const payload: ClientMessage = { type: 'chat', payload: { message } }
    ch.ws.send(JSON.stringify(payload))
  }

  function cancel() {
    const ch = activeChannel.value
    if (!ch.ws || ch.ws.readyState !== WebSocket.OPEN) return
    const payload: ClientMessage = { type: 'cancel', payload: {} }
    ch.ws.send(JSON.stringify(payload))
  }

  function sendUserResponse(interactionId: string, response: string | string[]) {
    const ch = activeChannel.value
    if (!ch.ws || ch.ws.readyState !== WebSocket.OPEN) return
    const payload: ClientMessage = {
      type: 'user_response',
      payload: { interaction_id: interactionId, response },
    }
    ch.ws.send(JSON.stringify(payload))
  }

  return {
    connected, isStreaming, turns, currentTurn, error, contextUsage,
    send, cancel, sendUserResponse,
  }
}

function findLastThinking(events: TurnEvent[]): ThinkingBlock | undefined {
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i].kind === 'thinking') {
      return events[i] as ThinkingBlock
    }
  }
  return undefined
}

function findRunningTool(events: TurnEvent[], toolName: string): ToolCall | undefined {
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i]
    if (e.kind === 'tool' && e.name === toolName && e.status === 'running') {
      return e as ToolCall
    }
  }
  return undefined
}
