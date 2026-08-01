import { reactive, computed, type Ref } from 'vue'
import { defineStore } from 'pinia'
import type {
  ServerEvent, ChatTurn, ToolCall, ThinkingBlock,
  TurnEvent, ContextUsage, AskUserEvent, MemoryToolEvent,
  ClientMessage, TokenEvent, PendingMessage,
  MessageQueuedEvent, PendingConsumedEvent, PendingSyncEvent, PendingCancelledEvent,
} from '@/types'
import { buildFlatMessage, parseReferences } from '@/utils/references'
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
  /** Agent 输出期间发送、等待注入的排队消息气泡 */
  pendingMessages: PendingMessage[]
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

  /** 按 turn.id 去重，清理旧 bug 留存的同 ID 重复条目。 */
  function dedupTurnsById(turns: ChatTurn[]): ChatTurn[] {
    const seen = new Set<string>()
    const result: ChatTurn[] = []
    let dupCount = 0
    for (const t of turns) {
      if (seen.has(t.id)) {
        dupCount++
        console.warn('[chatStore] dedupTurnsById: 发现重复 turn.id=%s, 已跳过', t.id)
      } else {
        seen.add(t.id)
        result.push(t)
      }
    }
    if (dupCount > 0) {
      console.warn('[chatStore] dedupTurnsById: 共清理 %d 个重复条目  session=%s', dupCount, /* sid not available here */ '')
    }
    return result
  }

  function getOrCreateChannel(sid: string): SessionChannel {
    if (!channels.has(sid)) {
      const cached = turnsCache.get(sid)
      // 去重：清理可能因旧 bug 留存的同 ID 重复 turns
      const deduped = cached ? dedupTurnsById(cached) : undefined
      console.debug('[chatStore] getOrCreateChannel: 创建新通道 session=%s, 缓存命中=%s, 缓存 turns=%d, 去重后=%d',
        sid, !!cached, cached ? cached.length : 0, deduped ? deduped.length : 0)
      channels.set(sid, {
        ws: null,
        connected: false,
        isStreaming: false,
        isAwaitingUser: false,
        turns: deduped ?? [],
        currentTurn: null,
        pendingMessages: [],
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
    console.debug('[chatStore] persistTurns: 持久化 session=%s, turns=%d, currentTurn=%s',
      sid, snapshot.length, ch.currentTurn?.id ?? 'null')
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

      // 从后端恢复的消息包含时间标记（如「（2026-07-29 Wed 14:30）」）和引用块，
      // 使用 parseReferences 提取纯净文本与引用，与 migrateLegacyTurn（localStorage 缓存）保持一致
      const { cleanText, refs } = parseReferences(msgs[i].content)
      const userMsg = refs.length > 0 ? cleanText : msgs[i].content.replace(TIME_SUFFIX_RE, '').trim()
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
              thinkingCount: 0,
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
        refs,
        events,
        finalAnswer,
      })
    }
    return turns
  }

  /** 正在从后端恢复中的会话集合，防止并发调用导致重复。 */
  const restoreInFlight = new Set<string>()

  /** 从后端 API 拉取消息并恢复到通道的 turns 中。 */
  async function restoreTurnsFromBackend(sid: string): Promise<void> {
    if (restoreInFlight.has(sid)) {
      console.warn('[chatStore] restoreTurnsFromBackend: 跳过, 正在恢复中 sid=%s', sid)
      return
    }
    restoreInFlight.add(sid)
    const ch = channels.get(sid)
    if (!ch) { console.warn('[chatStore] restoreTurnsFromBackend: 通道不存在 sid=%s', sid); restoreInFlight.delete(sid); return }
    if (ch.turns.length > 0) {
      console.warn('[chatStore] restoreTurnsFromBackend: 通道已有 turns(%d), 跳过恢复 sid=%s（若此日志未出现则问题不在此）', ch.turns.length, sid)
      restoreInFlight.delete(sid)
      return
    }
    // 若有 currentTurn（正在流式的轮次），说明会话仍「活着」，不应从后端恢复
    if (ch.currentTurn) {
      console.warn('[chatStore] restoreTurnsFromBackend: 有 currentTurn(%s), 跳过恢复 sid=%s', ch.currentTurn.id, sid)
      restoreInFlight.delete(sid)
      return
    }
    console.warn('[chatStore] restoreTurnsFromBackend: ⚡ 即将从后端恢复 sid=%s（当前 channels 数=%d）', sid, channels.size)
    try {
      console.debug('[chatStore] restoreTurnsFromBackend: 从后端获取消息 sid=%s', sid)
      const res = await sessionsApi.getMessages(sid)
      const turns = messagesToTurns(res.messages)
      // 再次检查：await 期间可能有其他调用已写入 turns
      if (turns.length > 0 && ch.turns.length === 0) {
        ch.turns.push(...turns)
        turnsCache.set(sid, [...ch.turns])
        saveTurnsToStorage(sid, [...ch.turns])
        console.warn('[chatStore] restoreTurnsFromBackend: ✅ 已恢复 %d 个轮次 sid=%s', turns.length, sid)
      } else {
        console.warn('[chatStore] restoreTurnsFromBackend: await 后有变化, turns=%d, backend返回=%d, 跳过 push sid=%s',
          ch.turns.length, turns.length, sid)
      }
    } catch (e) {
      console.warn('[chatStore] restoreTurnsFromBackend: 获取消息失败 sid=%s, error=%o', sid, e)
    } finally {
      restoreInFlight.delete(sid)
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
      if (ch.currentTurn) {
        ch.currentTurn.memorySearch = {
          status: 'searching',
          skipInteractionId: event.payload.interaction_id,
        }
      }
      return
    }
    if (event.type === 'memory_search_skipped') {
      if (ch.currentTurn) {
        ch.currentTurn.memorySearch = { status: 'skipped' }
      }
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

    // 排队消息事件：在 turn 守卫之前处理（可能 currentTurn 尚为 null）
    if (event.type === 'message_queued') {
      const me = event as MessageQueuedEvent
      // 竞态兜底：空闲路径可能已为该消息创建了 currentTurn，但后端实际入队了
      // → 该消息并非作为轮次处理，转为排队气泡
      if (ch.currentTurn && ch.currentTurn.id === me.payload.pending_id && ch.currentTurn.events.length === 0) {
        ch.currentTurn = null
        ch.isStreaming = false
      }
      if (!ch.pendingMessages.some(p => p.id === me.payload.pending_id)) {
        ch.pendingMessages.push({ id: me.payload.pending_id, text: me.payload.text, status: 'queued' })
      }
      return
    }

    if (event.type === 'pending_consumed') {
      const pe = event as PendingConsumedEvent
      const consumed = new Set(pe.payload.pending.map(p => p.pending_id))
      if (pe.payload.mode === 'mid_turn') {
        // 注入当前轮：从排队区移除，作为用户气泡插入工具之间的聊天流。
        // 文本含引用块，解析出干净文本与引用 chip（与普通用户气泡一致）。
        ch.pendingMessages = ch.pendingMessages.filter(p => !consumed.has(p.id))
        const turn = ch.currentTurn
        if (turn) {
          for (const item of pe.payload.pending) {
            const { cleanText, refs } = parseReferences(item.text)
            turn.events.push({ kind: 'user_message', content: cleanText, refs })
          }
        }
      } else if (pe.payload.mode === 'new_turn') {
        // 后端自动启动的合并轮：移除已消费气泡，创建 currentTurn（不调用 send）
        ch.pendingMessages = ch.pendingMessages.filter(p => !consumed.has(p.id))
        ch.error = null
        ch.currentTurn = {
          id: crypto.randomUUID(),
          userMessage: pe.payload.text || '(已合并消息)',
          refs: [],
          events: [],
          memoryEvents: [],
          finalAnswer: null,
        }
        ch.isStreaming = true
      }
      return
    }

    if (event.type === 'pending_sync') {
      const se = event as PendingSyncEvent
      ch.pendingMessages = se.payload.pending.map(p => ({ id: p.pending_id, text: p.text, status: 'queued' }))
      return
    }

    if (event.type === 'pending_cancelled') {
      const ce = event as PendingCancelledEvent
      const ids = new Set(ce.payload.pending_ids)
      ch.pendingMessages = ch.pendingMessages.filter(p => !ids.has(p.id))
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

    const flatMsg = buildFlatMessage(text, refs)
    // 客户端消息 ID：作为 client_msg_id 发送，后端复用作 pending_id，
    // 使 message_queued ack 与乐观气泡 id 精确对应。
    const clientMsgId = crypto.randomUUID()

    const payload: ClientMessage = {
      type: 'chat',
      payload: {
        message: flatMsg,
        private: ch.privateMode,
        skip_recall: ch.skipRecall,
        auto_approve: ch.autoApprove,
        provider_id: providerId,
        model_name: modelName,
        client_msg_id: clientMsgId,
        ...(imageRecognition && imagePaths?.length ? { image_recognition: true, image_refs: imagePaths } : {}),
      },
    }

    // Agent 输出期间（或已有排队消息）：挂起到队列，等待注入，不触碰 currentTurn
    if (ch.isStreaming || ch.pendingMessages.length > 0) {
      ch.pendingMessages.push({ id: clientMsgId, text, status: 'queued' })
      ch.ws.send(JSON.stringify(payload))
      return
    }

    // 空闲：正常创建轮次
    ch.isStreaming = true
    ch.error = null
    ch.currentTurn = {
      id: clientMsgId,
      userMessage: text,
      refs,
      imageRefs: imageRecognition && imagePaths?.length
        ? imagePaths.map(p => ({ type: 'file' as const, path: p, label: p.split(/[/\\]/).pop() || p }))
        : undefined,
      events: [],
      memoryEvents: [],
      finalAnswer: null,
    }
    ch.ws.send(JSON.stringify(payload))
  }

  function cancel(sid: string) {
    const ch = channels.get(sid)
    if (!ch?.ws || ch.ws.readyState !== WebSocket.OPEN) return
    ch.ws.send(JSON.stringify({ type: 'cancel', payload: {} } as ClientMessage))
  }

  /** 从排队队列移除一条消息（乐观移除 + 后端同步）。 */
  function removePendingMessage(sid: string, pendingId: string) {
    const ch = channels.get(sid)
    if (!ch) return
    ch.pendingMessages = ch.pendingMessages.filter(p => p.id !== pendingId)
    if (ch.ws?.readyState === WebSocket.OPEN) {
      ch.ws.send(JSON.stringify({ type: 'remove_pending', payload: { pending_id: pendingId } } as ClientMessage))
    }
  }

  /** 清空全部排队消息（乐观清空 + 后端同步，不取消正在运行的 Agent）。 */
  function clearPendingMessages(sid: string) {
    const ch = channels.get(sid)
    if (!ch) return
    ch.pendingMessages = []
    if (ch.ws?.readyState === WebSocket.OPEN) {
      ch.ws.send(JSON.stringify({ type: 'clear_pending', payload: {} } as ClientMessage))
    }
  }

  function skipMemorySearch(sid: string) {
    const ch = channels.get(sid)
    if (!ch?.ws || ch.ws.readyState !== WebSocket.OPEN) return
    const interactionId = ch.currentTurn?.memorySearch?.status === 'searching'
      ? ch.currentTurn.memorySearch.skipInteractionId
      : undefined
    if (!interactionId) return
    ch.ws.send(JSON.stringify({
      type: 'skip_memory_search',
      payload: { interaction_id: interactionId },
    } as ClientMessage))
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
    skipMemorySearch,
    sendUserResponse,
    removeTurns,
    updateAutoApprove,
    removePendingMessage,
    clearPendingMessages,
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
