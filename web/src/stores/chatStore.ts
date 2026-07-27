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
import { sessionsApi } from '@/api/sessions'
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
  let loadedCount = 0
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (key && key.startsWith(TURNS_KEY_PREFIX)) {
      const sid = key.slice(TURNS_KEY_PREFIX.length)
      try {
        const raw = localStorage.getItem(key) || '[]'
        const data = JSON.parse(raw)
        if (Array.isArray(data)) {
          map.set(sid, data.map(migrateLegacyTurn))
          loadedCount++
          console.debug('[chatStore] loadAllTurnsFromStorage: 已加载 session=%s, turns=%d', sid, data.length)
        }
      } catch (e) {
        console.warn('[chatStore] loadAllTurnsFromStorage: 跳过损坏的缓存 key=%s, error=%o', key, e)
      }
    }
  }
  console.debug('[chatStore] loadAllTurnsFromStorage: 完成, 共加载 %d 个会话的缓存', loadedCount)
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
  skipRecall: boolean
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
      console.debug('[chatStore] getOrCreateChannel: 创建新通道 session=%s, 缓存命中=%s, turns=%d',
        sid, !!cached, cached ? cached.length : 0)
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
        skipRecall: false,
        autoApprove: false,
      })
    } else {
      const ch = channels.get(sid)!
      console.debug('[chatStore] getOrCreateChannel: 复用已有通道 session=%s, turns=%d, connected=%s',
        sid, ch.turns.length, ch.connected)
    }
    return channels.get(sid)!
  }

  function saveTurnsToStorage(sid: string, data: ChatTurn[]) {
    const key = TURNS_KEY_PREFIX + sid
    try {
      localStorage.setItem(key, JSON.stringify(data))
      console.debug('[chatStore] saveTurnsToStorage: 已写入 key=%s, turns=%d, bytes=%d',
        key, data.length, JSON.stringify(data).length)
    } catch (e) {
      console.warn('[chatStore] saveTurnsToStorage: 写入失败 key=%s, error=%o', key, e)
    }
  }

  function persistTurns(sid: string) {
    const ch = channels.get(sid)
    if (!ch) {
      console.debug('[chatStore] persistTurns: 跳过, 通道不存在 sid=%s', sid)
      return
    }
    const snapshot = [...ch.turns]
    turnsCache.set(sid, snapshot)
    console.debug('[chatStore] persistTurns: 持久化 session=%s, turns=%d', sid, snapshot.length)
    saveTurnsToStorage(sid, snapshot)
  }

  function removeTurnsFromStorage(sid: string) {
    const key = TURNS_KEY_PREFIX + sid
    console.debug('[chatStore] removeTurnsFromStorage: 删除缓存 key=%s', key)
    localStorage.removeItem(key)
  }

  // ── 从后端恢复历史消息 ──

  /**
   * 将后端返回的扁平消息列表按 human→ai 配对，转换为 ChatTurn[]。
   * tool 消息作为 ToolCall 事件嵌入所在轮次。
   */
  function messagesToTurns(
    msgs: Array<{ role: string; content: string }>,
  ): ChatTurn[] {
    const turns: ChatTurn[] = []
    let i = 0
    while (i < msgs.length) {
      // 找到下一条 human 消息
      if (msgs[i].role !== 'human') { i++; continue }

      const userMsg = msgs[i].content
      const events: TurnEvent[] = []
      let finalAnswer: string | null = null
      i++

      // 收集 human 之后的所有消息直到下一条 human 或结尾
      while (i < msgs.length && msgs[i].role !== 'human') {
        const m = msgs[i]
        if (m.role === 'tool') {
          events.push({
            kind: 'tool',
            name: '',
            input: '',
            output: m.content,
            elapsed: null,
            status: 'done',
          } as ToolCall)
        } else if (m.role === 'ai') {
          // 如果有多个 ai 段，最后一段作为 finalAnswer，前面的作为 thinking
          if (finalAnswer !== null) {
            // 已有 finalAnswer，前面的 ai 内容视为 thinking
            events.push({
              kind: 'thinking',
              tokens: finalAnswer,
              done: true,
              becameAnswer: false,
            } as ThinkingBlock)
          }
          finalAnswer = m.content
        }
        i++
      }

      turns.push({
        id: crypto.randomUUID(),
        userMessage: userMsg,
        refs: [],
        events,
        finalAnswer,
      })
    }
    return turns
  }

  /** 从后端 API 拉取消息并恢复到通道的 turns 中。 */
  async function restoreTurnsFromBackend(sid: string): Promise<void> {
    const ch = channels.get(sid)
    if (!ch) return
    if (ch.turns.length > 0) {
      console.debug('[chatStore] restoreTurnsFromBackend: 通道已有 turns, 跳过 sid=%s, turns=%d', sid, ch.turns.length)
      return
    }
    try {
      console.debug('[chatStore] restoreTurnsFromBackend: 从后端获取消息 sid=%s', sid)
      const res = await sessionsApi.getMessages(sid)
      const turns = messagesToTurns(res.messages)
      if (turns.length > 0) {
        ch.turns.push(...turns)
        turnsCache.set(sid, [...ch.turns])
        saveTurnsToStorage(sid, [...ch.turns])
        console.debug('[chatStore] restoreTurnsFromBackend: 已恢复 %d 个轮次 sid=%s', turns.length, sid)
      }
    } catch (e) {
      console.warn('[chatStore] restoreTurnsFromBackend: 获取消息失败 sid=%s, error=%o', sid, e)
    }
  }

  // ── WebSocket 生命周期 ──

  function connectSession(sid: string) {
    if (!isValidSessionId(sid)) {
      console.debug('[chatStore] connectSession: 跳过, sid=%s 格式无效', sid)
      return
    }
    const ch = getOrCreateChannel(sid)
    if (ch.ws?.readyState === WebSocket.OPEN) {
      console.debug('[chatStore] connectSession: WS 已打开, 跳过 sid=%s', sid)
      return
    }

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const token = getToken()
    const wsUrl = `${protocol}//${location.host}/ws/chat/${sid}`
    console.debug('[chatStore] connectSession: 创建 WebSocket sid=%s, url=%s', sid, wsUrl)
    ch.ws = new WebSocket(wsUrl, [token])

    ch.ws.onopen = () => {
      ch.connected = true
      console.debug('[chatStore] WS onopen: sid=%s', sid)
      if (ch.reconnectTimer) {
        clearTimeout(ch.reconnectTimer)
        ch.reconnectTimer = null
      }
    }

    ch.ws.onclose = (ev) => {
      ch.connected = false
      console.debug('[chatStore] WS onclose: sid=%s, code=%d, reason=%s', sid, ev.code, ev.reason)
      ch.reconnectTimer = setTimeout(() => connectSession(sid), 3000)
    }

    ch.ws.onmessage = (event) => {
      try {
        const msg: ServerEvent = JSON.parse(event.data)
        console.debug('[chatStore] WS onmessage: sid=%s, type=%s', sid, msg.type)
        handleEventForChannel(sid, msg)
      } catch (e) {
        console.error('[chatStore] WS message error:', e)
      }
    }
  }

  function ensureConnected(sid: string) {
    if (!sid || !isValidSessionId(sid)) {
      console.debug('[chatStore] ensureConnected: 跳过, sid=%s, valid=%s', sid, sid ? isValidSessionId(sid) : false)
      return
    }
    const ch = getOrCreateChannel(sid)
    if (ch.initialized) {
      console.debug('[chatStore] ensureConnected: 已初始化, 跳过 sid=%s', sid)
      return
    }
    ch.initialized = true
    console.debug('[chatStore] ensureConnected: 初始化并连接 sid=%s', sid)
    connectSession(sid)
  }

  function disconnectChannel(sid: string) {
    const ch = channels.get(sid)
    if (!ch) {
      console.debug('[chatStore] disconnectChannel: 通道不存在 sid=%s', sid)
      return
    }
    console.debug('[chatStore] disconnectChannel: 断开 sid=%s', sid)
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

    // 语义记忆搜索事件：直接更新 currentTurn
    if (event.type === 'memory_search_start') {
      if (ch.currentTurn) ch.currentTurn.memorySearch = { status: 'searching' }
      return
    }
    if (event.type === 'memory_search_done') {
      if (ch.currentTurn) {
        ch.currentTurn.memorySearch = { status: 'done', total: event.payload.total, fresh: event.payload.fresh }
      }
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
        skip_recall: ch.skipRecall,
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
    restoreTurnsFromBackend,
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
