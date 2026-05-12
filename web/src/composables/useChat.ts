import { ref, reactive, watch, onUnmounted, type Ref } from 'vue'
import type { ClientMessage, ServerEvent, ChatTurn, ToolCall, ThinkingBlock, TurnEvent } from '@/types'

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

const turnsCache = loadAllTurnsFromStorage()

export function useChat(sessionId: Ref<string>) {
  const ws = ref<WebSocket | null>(null)
  const connected = ref(false)
  const isStreaming = ref(false)
  const turns = reactive<ChatTurn[]>([])
  const currentTurn = ref<ChatTurn | null>(null)
  const error = ref<string | null>(null)
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  function persistTurns() {
    const snapshot = [...turns]
    turnsCache.set(sessionId.value, snapshot)
    saveTurnsToStorage(sessionId.value, snapshot)
  }

  function connect() {
    if (ws.value?.readyState === WebSocket.OPEN) return

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${location.host}/ws/chat/${sessionId.value}`

    ws.value = new WebSocket(url)

    ws.value.onopen = () => {
      connected.value = true
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
    }

    ws.value.onclose = () => {
      connected.value = false
      reconnectTimer = setTimeout(connect, 3000)
    }

    ws.value.onmessage = (event) => {
      const msg: ServerEvent = JSON.parse(event.data)
      handleEvent(msg)
    }
  }

  function send(message: string) {
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) return
    isStreaming.value = true
    error.value = null

    const turn: ChatTurn = {
      id: crypto.randomUUID(),
      userMessage: message,
      events: [],
      finalAnswer: null,
    }
    currentTurn.value = turn

    const payload: ClientMessage = { type: 'chat', payload: { message } }
    ws.value.send(JSON.stringify(payload))
  }

  function cancel() {
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) return
    const payload: ClientMessage = { type: 'cancel', payload: {} }
    ws.value.send(JSON.stringify(payload))
  }

  function handleEvent(event: ServerEvent) {
    const turn = currentTurn.value
    if (!turn) return

    switch (event.type) {
      case 'thinking_start':
        turn.events.push({ kind: 'thinking', tokens: '', done: false })
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

      case 'answer':
        turn.finalAnswer = event.payload.content
        break

      case 'done':
        if (currentTurn.value) {
          turns.push(currentTurn.value)
          currentTurn.value = null
        }
        isStreaming.value = false
        persistTurns()
        break

      case 'error':
        error.value = event.payload.message
        isStreaming.value = false
        break

      case 'pong':
        break
    }
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    ws.value?.close()
    ws.value = null
    connected.value = false
  }

  watch(
    sessionId,
    (newId, oldId) => {
      // 切出旧会话前持久化
      if (oldId) {
        turnsCache.set(oldId, [...turns])
        saveTurnsToStorage(oldId, [...turns])
      }
      disconnect()
      // 恢复新会话消息（优先内存缓存，其次 localStorage 已在模块加载时读入）
      const cached = newId ? turnsCache.get(newId) : undefined
      turns.splice(0, turns.length)
      if (cached) {
        turns.push(...cached)
      }
      currentTurn.value = null
      error.value = null
      if (newId) {
        connect()
      }
    },
    { immediate: true }
  )

  onUnmounted(() => disconnect())

  return { connected, isStreaming, turns, currentTurn, error, send, cancel, connect, disconnect }
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
