import { reactive, computed, watch, nextTick, type Ref } from 'vue'
import type { ClientMessage, ServerEvent, ChatTurn, ToolCall, ThinkingBlock, TurnEvent, ContextUsage, TokenEvent, AnswerEvent, ErrorEvent, DoneEvent, AskUserEvent, MemoryToolEvent, MemoryToolStartEvent, MemoryToolEndEvent, MemoryToolErrorEvent, MemoryStartEvent, MemoryDoneEvent } from '@/types'
import { refreshSessions, switchSession } from '@/composables/useSession'
import { buildFlatMessage, buildTimestamp, parseReferences } from '@/utils/references'
import type { ParsedRef } from '@/utils/references'
import { getToken } from '@/api'
/** 匹配旧格式尾缀（用于 localStorage 迁移） */
const TIME_SUFFIX_RE = /（\d{4}-\d{2}-\d{2} \w{3} \d{2}:\d{2}）$/

export const TURNS_KEY_PREFIX = 'sonetto_turns_'

/** 将旧格式 turn（userMessage 含 __refs__ 和时间尾缀）迁移为新格式 */
function migrateLegacyTurn(turn: any): ChatTurn {
  if (Array.isArray(turn.refs)) {
    return { memoryEvents: [], ...turn } as ChatTurn
  }
  // 旧格式：从 userMessage 中提取 refs 和时间尾缀
  const prevMsg = (turn.userMessage ?? '') as string
  const { cleanText, refs } = parseReferences(prevMsg || '')
  const text = refs.length > 0 ? cleanText : prevMsg.replace(TIME_SUFFIX_RE, '')
  return { ...turn, userMessage: text, refs, memoryEvents: [] }
}

// 从 localStorage 恢复所有会话的消息缓存（页面刷新后仍保留）
function loadAllTurnsFromStorage(): Map<string, ChatTurn[]> {
  const map = new Map<string, ChatTurn[]>()
  const keysFound: string[] = []
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (key && key.startsWith(TURNS_KEY_PREFIX)) {
      keysFound.push(key)
      const sid = key.slice(TURNS_KEY_PREFIX.length)
      try {
        const raw = localStorage.getItem(key) || '[]'
        const data = JSON.parse(raw)
        if (Array.isArray(data)) {
          const migrated = data.map(migrateLegacyTurn)
          console.log(`[useChat:load] 从 localStorage 加载会话 ${sid}: ${data.length} 条 turn (迁移 ${migrated.length}), 序列化长度 ${raw.length}`)
          map.set(sid, migrated)
        } else {
          console.warn(`[useChat:load] 键 ${key} 的数据不是数组，跳过`)
        }
      } catch (e) {
        console.error(`[useChat:load] 解析 localStorage 键 ${key} 失败:`, e)
      }
    }
  }
  console.log(`[useChat:load] localStorage 中共 ${keysFound.length} 个 ${TURNS_KEY_PREFIX}* 键, 恢复 ${map.size} 个会话的缓存`)
  return map
}

function saveTurnsToStorage(sid: string, data: ChatTurn[]) {
  const key = TURNS_KEY_PREFIX + sid
  try {
    const serialized = JSON.stringify(data)
    const size = new Blob([serialized]).size
    console.log(`[useChat:save] 保存会话 ${sid} 到 localStorage: ${data.length} 条 turn, 约 ${(size / 1024).toFixed(1)} KB, key=${key}`)
    localStorage.setItem(key, serialized)
  } catch (e) {
    console.error(`[useChat:save] 保存会话 ${sid} 到 localStorage 失败 (key=${key}):`, e)
    // 尝试估算 localStorage 用量
    let total = 0
    for (let i = 0; i < localStorage.length; i++) {
      const k = localStorage.key(i)
      if (k) total += k.length + (localStorage.getItem(k) || '').length
    }
    console.warn(`[useChat:save] localStorage 当前总估算用量: ${(total * 2 / 1024).toFixed(1)} KB`)
  }
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
  // 先清除 onclose，再手动关闭 WS — 防止 onclose 触发意外重连
  if (ch.ws) {
    ch.ws.onclose = null
    ch.ws.close()
    ch.ws = null
  }
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
  isAwaitingUser: boolean
  turns: ChatTurn[]
  currentTurn: ChatTurn | null
  error: string | null
  contextUsage: ContextUsage | null
  taskTrackerData: Record<string, unknown> | null
  reconnectTimer: ReturnType<typeof setTimeout> | null
  initialized: boolean
  _awaitingToolName: string | null
  parentSessionId: string | null  // sub-agent 用：完成时切回主会话
  privateMode: boolean
  autoApprove: boolean
}

const channels = reactive(new Map<string, SessionChannel>())

// 所有 Session 的连接/流式状态（模块级，供 sidebar 使用）
export const allSessionStatuses = computed(() => {
  const map: Record<string, { connected: boolean; isStreaming: boolean; isAwaitingUser: boolean }> = {}
  for (const [sid, ch] of channels) {
    map[sid] = { connected: ch.connected, isStreaming: ch.isStreaming, isAwaitingUser: ch.isAwaitingUser }
  }
  return map
})

function getOrCreateChannel(sid: string): SessionChannel {
  if (!channels.has(sid)) {
    console.log(`[useChat:channel] 创建新通道 sid="${sid}"`)
    channels.set(sid, {
      ws: null,
      connected: false,
      isStreaming: false,
      isAwaitingUser: false,
      turns: [] as ChatTurn[],
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

function persistTurns(sid: string) {
  const ch = channels.get(sid)
  if (!ch) {
    console.warn(`[useChat:persist] 跳过保存 sid="${sid}": 通道不存在`)
    return
  }
  const snapshot = [...ch.turns]
  console.log(`[useChat:persist] 持久化会话 ${sid}: ${snapshot.length} 条 turn`)
  turnsCache.set(sid, snapshot)
  saveTurnsToStorage(sid, snapshot)
}

// ── WebSocket 生命周期（每 Session 独立管理） ──────────────

/** 会话 ID 格式验证：由后端 uuid.uuid4().hex 生成（32 位 hex） */
const SID_RE = /^[0-9a-f]{32}$/i

function isValidSessionId(sid: string): boolean {
  return SID_RE.test(sid)
}

function connectSession(sid: string) {
  if (!isValidSessionId(sid)) {
    console.error(`[useChat] 拒绝连接：非法的 sessionId "${sid}"`)
    return
  }
  const ch = getOrCreateChannel(sid)
  if (ch.ws?.readyState === WebSocket.OPEN) return

  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const token = getToken()
  const url = `${protocol}//${location.host}/ws/chat/${sid}`
  ch.ws = new WebSocket(url, [token])

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

export function ensureConnected(sid: string) {
  if (!sid) {
    console.warn(`[useChat:ensureConnected] 跳过空 sid`)
    return
  }
  if (!isValidSessionId(sid)) {
    console.error(`[useChat:ensureConnected] 拒绝连接：非法的 sessionId "${sid}"`)
    return
  }
  const ch = getOrCreateChannel(sid)
  if (ch.initialized) {
    console.log(`[useChat:ensureConnected] 会话 ${sid} 已初始化, 跳过`)
    return
  }
  console.log(`[useChat:ensureConnected] 初始化会话 ${sid} 的 WebSocket 连接`)
  ch.initialized = true
  connectSession(sid)
}

// ── 事件路由 ──────────────────────────────────────────────

/** read_memories 是纯读取操作，前端无需显示其执行状态。 */
function skipReadMemories(payload: { tool_name: string }): boolean {
  return payload.tool_name === 'read_memories'
}

/** 后台记忆 consumer 事件类型。 */
type MemoryEventType = 'memory_start' | 'memory_tool_start' | 'memory_tool_end' | 'memory_tool_error' | 'memory_done'

/** 后台记忆 consumer 事件处理器签名。 */
type MemoryEventHandler = (ch: SessionChannel, sid: string, event: ServerEvent) => void

/** 记忆事件处理器注册表。新增记忆事件类型只需在此注册，调用方守卫自动覆盖。 */
const memoryHandlers = new Map<MemoryEventType, MemoryEventHandler>([
  ['memory_start', handleMemoryStart],
  ['memory_tool_start', handleMemoryToolStart],
  ['memory_tool_end', handleMemoryToolEnd],
  ['memory_tool_error', handleMemoryToolError],
  ['memory_done', handleMemoryDone],
])

/** 事件路由处理器签名（turn 已由调用方守卫保证存在）。 */
type TurnEventHandler = (ch: SessionChannel, sid: string, turn: ChatTurn, event: ServerEvent) => void

/** 事件路由处理器注册表。 */
const turnHandlers = new Map<string, TurnEventHandler>([
  ['thinking_start', handleThinkingStart],
  ['token', handleToken],
  ['thinking_end', handleThinkingEnd],
  ['tool_start', handleToolStart],
  ['tool_end', handleToolEnd],
  ['tool_error', handleToolError],
  ['answer', handleAnswer],
  ['done', handleDone],
  ['error', handleError],
  ['ask_user', handleAskUser],
])

function handleEventForChannel(sid: string, event: ServerEvent) {
  const ch = channels.get(sid)
  if (!ch) return

  // context_usage 可以在无活跃轮次时接收（如连接初始化）
  if (event.type === 'context_usage') {
    ch.contextUsage = event.payload
    return
  }

  // sub_session_created 可能在任何时候到达（主 Agent 调用 call_sub_agent）
  if (event.type === 'sub_session_created') {
    const subId = event.payload.sub_session_id
    const parentId = event.payload.parent_session_id
    void refreshSessions()
    ensureConnected(subId)

    // 初始化子会话的 currentTurn，否则子 Agent 推送的所有事件都被丢弃
    const subCh = getOrCreateChannel(subId)
    subCh.parentSessionId = parentId
    subCh.isStreaming = true
    subCh.currentTurn = {
      id: crypto.randomUUID(),
      userMessage: event.payload.task || '(子 Agent 任务)',
      refs: [],
      events: [],
      memoryEvents: [],
      finalAnswer: null,
    }

    void switchSession(subId)
    return
  }

  // 后台记忆 consumer 事件可能在 done 事件之后到达（currentTurn 已清空），
  // 必须在 const turn = ch.currentTurn 守卫之前处理，通过 turn_id 自行查找目标。
  const memoryHandler = memoryHandlers.get(event.type as MemoryEventType)
  if (memoryHandler) {
    memoryHandler(ch, sid, event)
    return
  }

  const turn = ch.currentTurn
  if (!turn) return

  const turnHandler = turnHandlers.get(event.type)
  if (turnHandler) {
    turnHandler(ch, sid, turn, event)
  }
}

/** 后台记忆 consumer 开始处理本轮对话：压入「处理中」占位条目。 */
function handleMemoryStart(ch: SessionChannel, sid: string, event: ServerEvent): void {
  const me = event as MemoryStartEvent
  console.log(`[ltm-fe] memory_start session=${sid} turn_id=${me.payload.turn_id}`)
  const targetTurn = findTurnByBackendId(ch, me.payload.turn_id)
  if (!targetTurn) { console.log(`[ltm-fe] NO turn found for ${me.payload.turn_id}`); return }
  if (!targetTurn.memoryEvents) targetTurn.memoryEvents = []
  targetTurn.memoryEvents.push({
    kind: 'memory_tool', name: 'memory_processing', input: '', output: null, elapsed: null, status: 'running',
  })
}

/** 后台记忆 consumer 开始调用 CRUD 工具：压入 running 状态工具事件。 */
function handleMemoryToolStart(ch: SessionChannel, sid: string, event: ServerEvent): void {
  const me = event as MemoryToolStartEvent
  if (skipReadMemories(me.payload)) return
  console.log(`[ltm-fe] memory_tool_start session=${sid} turn_id=${me.payload.turn_id} tool=${me.payload.tool_name}`)
  const targetTurn = findTurnByBackendId(ch, me.payload.turn_id)
  if (!targetTurn) { console.log(`[ltm-fe] NO turn found for ${me.payload.turn_id}`); return }
  targetTurn.memoryEvents?.push({
    kind: 'memory_tool', name: me.payload.tool_name, input: me.payload.input,
    output: null, elapsed: null, status: 'running',
  })
}

/** 后台记忆 consumer 的 CRUD 工具执行完毕：更新匹配事件为 done。 */
function handleMemoryToolEnd(ch: SessionChannel, sid: string, event: ServerEvent): void {
  const me = event as MemoryToolEndEvent
  if (skipReadMemories(me.payload)) return
  console.log(`[ltm-fe] memory_tool_end session=${sid} turn_id=${me.payload.turn_id} tool=${me.payload.tool_name}`)
  const targetTurn = findTurnByBackendId(ch, me.payload.turn_id)
  if (!targetTurn) { console.log(`[ltm-fe] NO turn`); return }
  const mt = findRunningMemoryTool(targetTurn.memoryEvents ?? [], me.payload.tool_name)
  if (mt) { mt.output = me.payload.output; mt.elapsed = me.payload.elapsed; mt.status = 'done' }
  if (ch.turns.includes(targetTurn as ChatTurn)) persistTurns(sid)
}

/** 后台记忆 consumer 的 CRUD 工具出错：更新匹配事件为 error。 */
function handleMemoryToolError(ch: SessionChannel, sid: string, event: ServerEvent): void {
  const me = event as MemoryToolErrorEvent
  if (skipReadMemories(me.payload)) return
  const targetTurn = findTurnByBackendId(ch, me.payload.turn_id)
  if (!targetTurn) return
  const mt = findRunningMemoryTool(targetTurn.memoryEvents ?? [], me.payload.tool_name)
  if (mt) mt.status = 'error'
  if (ch.turns.includes(targetTurn as ChatTurn)) persistTurns(sid)
}

/** 后台记忆 consumer 处理完毕：移除「处理中」占位，无实际工具事件时渲染 memory_review。 */
function handleMemoryDone(ch: SessionChannel, sid: string, event: ServerEvent): void {
  const me = event as MemoryDoneEvent
  console.log(`[ltm-fe] memory_done session=${sid} turn_id=${me.payload.turn_id}`)
  const targetTurn = findTurnByBackendId(ch, me.payload.turn_id)
  if (!targetTurn) { console.log(`[ltm-fe] NO turn`); return }
  // 移除「处理中」占位条目
  const realEvents = (targetTurn.memoryEvents ?? []).filter(e => e.name !== 'memory_processing')
  targetTurn.memoryEvents = realEvents
  if (realEvents.length === 0) {
    targetTurn.memoryEvents = [{
      kind: 'memory_tool', name: 'memory_review', input: '', output: '', elapsed: null, status: 'done',
    }]
    console.log(`[ltm-fe] added memory_review`)
  }
  if (ch.turns.includes(targetTurn as ChatTurn)) persistTurns(sid)
}

/** thinking_start：压入思考块。 */
function handleThinkingStart(ch: SessionChannel, _sid: string, turn: ChatTurn, _event: ServerEvent): void {
  turn.events.push({ kind: 'thinking', tokens: '', done: false, becameAnswer: false })
}

/** token：追加到最后一个思考块。 */
function handleToken(ch: SessionChannel, _sid: string, turn: ChatTurn, event: ServerEvent): void {
  const lastThink = findLastThinking(turn.events)
  if (lastThink) {
    lastThink.tokens += (event as TokenEvent).payload.token
  }
}

/** thinking_end：标记最后一个思考块完成。 */
function handleThinkingEnd(ch: SessionChannel, _sid: string, turn: ChatTurn, event: ServerEvent): void {
  const lastThink = findLastThinking(turn.events)
  if (lastThink) {
    lastThink.done = true
  }
}

/** tool_start：压入 running 状态工具调用。 */
function handleToolStart(ch: SessionChannel, sid: string, turn: ChatTurn, event: ServerEvent): void {
  const tsEvent = event as { type: 'tool_start'; payload: { call_id: string; tool_name: string; input: string } }
  console.log('[useChat] tool_start:', tsEvent.payload.tool_name, { input: tsEvent.payload.input, call_id: tsEvent.payload.call_id, session: sid })
  turn.events.push({
    kind: 'tool',
    name: tsEvent.payload.tool_name,
    input: tsEvent.payload.input,
    output: null,
    elapsed: null,
    status: 'running',
    callId: tsEvent.payload.call_id,
  })
}

/** tool_end：更新匹配工具调用为 done，提取 tool_data，处理 ask_user 状态恢复。 */
function handleToolEnd(ch: SessionChannel, sid: string, turn: ChatTurn, event: ServerEvent): void {
  const teEvent = event as { type: 'tool_end'; payload: { call_id: string; tool_name: string; output: string; elapsed: number; tool_data?: Record<string, unknown> } }
  // 精确匹配：优先用 call_id，降级用 heuristic
  const tc = findToolByCallId(turn.events, teEvent.payload.call_id)
    ?? findBestMatchingTool(turn.events, teEvent.payload.tool_name)
  if (tc) {
    tc.output = teEvent.payload.output
    tc.elapsed = teEvent.payload.elapsed
    tc.status = 'done'
    if (teEvent.payload.tool_data) {
      tc.toolData = teEvent.payload.tool_data
      if (teEvent.payload.tool_name === 'task_tracker' && teEvent.payload.tool_data) {
        ch.taskTrackerData = teEvent.payload.tool_data as Record<string, unknown>
      }
    }
    console.log(`[useChat] tool_end: "${teEvent.payload.tool_name}"`, {
      output_len: (teEvent.payload.output || '').length,
      output_preview: (teEvent.payload.output || '').slice(0, 100),
      has_tool_data: !!teEvent.payload.tool_data,
      elapsed: teEvent.payload.elapsed,
      session: sid,
    })
  }
  // ask_user 工具执行完毕 → 用户已回应，回到工作态
  if (ch.isAwaitingUser && teEvent.payload.tool_name === ch._awaitingToolName) {
    ch.isAwaitingUser = false
    ch._awaitingToolName = null
  }
}

/** tool_error：更新匹配工具调用为 error。 */
function handleToolError(ch: SessionChannel, _sid: string, turn: ChatTurn, event: ServerEvent): void {
  const teEvent = event as { type: 'tool_error'; payload: { call_id: string; tool_name: string; error: string } }
  const tc = findToolByCallId(turn.events, teEvent.payload.call_id)
    ?? findBestMatchingTool(turn.events, teEvent.payload.tool_name)
  if (tc) {
    tc.status = 'error'
  }
}

/** answer：标记思考块为 becameAnswer，设置 finalAnswer。 */
function handleAnswer(ch: SessionChannel, _sid: string, turn: ChatTurn, event: ServerEvent): void {
  const lastThink = findLastThinking(turn.events)
  if (lastThink) {
    lastThink.becameAnswer = true
  }
  turn.finalAnswer = (event as AnswerEvent).payload.content
}

/** done：finalize 当前轮次，持久化，刷新会话列表。 */
function handleDone(ch: SessionChannel, sid: string, turn: ChatTurn, event: ServerEvent): void {
  const de = event as DoneEvent
  ch.isAwaitingUser = false
  ch._awaitingToolName = null
  if (de.payload.context_usage) {
    ch.contextUsage = de.payload.context_usage
  }
  // 存储后端 turn_id，用于关联后台记忆 consumer 的事件
  if (de.payload.turn_id) {
    turn.turnId = de.payload.turn_id
    console.log(`[ltm-fe] turnId set on turn.id=${turn.id}: ${turn.turnId}`)
  }
  const lastThink = findLastThinking(turn.events)
  const trackBecame = lastThink?.becameAnswer
  console.log(`[useChat:done] 会话 ${sid}: becameAnswer=${trackBecame}, events=${turn.events.length}, finalAnswer=${turn.finalAnswer?.slice(0, 50) ?? 'null'}`)
  if (trackBecame) {
    const turnToFinalize = turn
    void nextTick(() => {
      setTimeout(() => {
        console.log(`[useChat:done] becameAnswer 分支执行 persist (会话 ${sid})`)
        ch.turns.push(turnToFinalize)
        ch.currentTurn = null
        ch.isStreaming = false
        if (!ch.privateMode) { persistTurns(sid) }
      }, 420)
    })
  } else {
    console.log(`[useChat:done] 直接分支执行 persist (会话 ${sid})`)
    ch.turns.push(turn)
    ch.currentTurn = null
    ch.isStreaming = false
    if (!ch.privateMode) { persistTurns(sid) }
  }
  void refreshSessions()  // 轮次结束，刷新会话列表以更新 message_count
  // 子 Agent 完成 → 自动切回主会话
  if (ch.parentSessionId) {
    setTimeout(() => switchSession(ch.parentSessionId!), 500)
  }
}

/** error：清除流式状态，设置错误信息。 */
function handleError(ch: SessionChannel, _sid: string, _turn: ChatTurn, event: ServerEvent): void {
  ch.isAwaitingUser = false
  ch._awaitingToolName = null
  ch.error = (event as ErrorEvent).payload.message
  ch.isStreaming = false
}

/** ask_user：设置交互等待状态，在 running 工具上挂载 interaction。 */
function handleAskUser(ch: SessionChannel, sid: string, turn: ChatTurn, event: ServerEvent): void {
  const ae = event as AskUserEvent
  ch.isAwaitingUser = true
  ch._awaitingToolName = ae.payload.tool_name
  console.log('[useChat] received ask_user event:', {
    tool_name: ae.payload.tool_name,
    question: ae.payload.question?.slice(0, 50),
    mode: ae.payload.mode,
    interaction_id: ae.payload.interaction_id,
    session: sid,
  })
  const runningTool = findFirstRunningToolForInteraction(turn.events, ae.payload.tool_name)
  console.log('[useChat] findFirstRunningToolForInteraction result:', runningTool ? {
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
      code: ae.payload.code,
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
  const taskTrackerData = computed(() => activeChannel.value.taskTrackerData)

  const privateMode = computed(() => activeChannel.value.privateMode)
  const autoApprove = computed(() => activeChannel.value.autoApprove)

  function setPrivateMode(val: boolean) {
    activeChannel.value.privateMode = val
  }

  function setAutoApprove(val: boolean) {
    activeChannel.value.autoApprove = val
    const ch = activeChannel.value
    if (ch.ws && ch.ws.readyState === WebSocket.OPEN) {
      ch.ws.send(JSON.stringify({
        type: 'update_auto_approve',
        payload: { auto_approve: val }
      }))
    }
  }

  // Session 切换：只确保新 Session 的 WS 连接，不断开旧的
  watch(
    sessionId,
    (newId, oldId) => {
      console.log(`[useChat:watch] sessionId 变化: "${oldId}" → "${newId}"`)
      if (oldId) {
        console.log(`[useChat:watch] 在切换前持久化旧会话 "${oldId}"`)
        persistTurns(oldId)
      }
      ensureConnected(newId)
      // 恢复新会话的消息缓存（页面刷新场景）
      const cached = turnsCache.get(newId)
      const ch = getOrCreateChannel(newId)
      if (cached) {
        console.log(`[useChat:watch] 找到会话 ${newId} 的缓存: ${cached.length} 条 turn, 通道已有 ${ch.turns.length} 条`)
        if (ch.turns.length === 0) {
          console.log(`[useChat:watch] 恢复缓存: 将 ${cached.length} 条 turn 推入通道`)
          ch.turns.push(...cached)
          console.log(`[useChat:watch] 恢复后通道 turns.length = ${ch.turns.length}`)
        } else {
          console.log(`[useChat:watch] 跳过恢复: 通道已有数据`)
        }
      } else {
        console.log(`[useChat:watch] 未找到会话 ${newId} 的缓存, sessionId="${sessionId.value}"`)
        // 调试：列出 turnsCache 中所有可用的 key
        const available = Array.from(turnsCache.keys())
        console.log(`[useChat:watch] turnsCache 可用键:`, available.length ? available : '(空)')
      }
    },
    { immediate: true }
  )

  function send(text: string, refs: ParsedRef[] = [], providerId?: string, modelName?: string, imageRecognition?: boolean, imagePaths?: string[]) {
    const ch = activeChannel.value
    if (!ch.ws || ch.ws.readyState !== WebSocket.OPEN) {
      console.warn(`[useChat:send] WebSocket 未就绪, readyState=${ch.ws?.readyState}, session=${sessionId.value}`)
      return
    }
    ch.isStreaming = true
    ch.error = null

    const timestamp = buildTimestamp()
    const flatMsg = buildFlatMessage(text, timestamp, refs)

    const turn: ChatTurn = {
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
    ch.currentTurn = turn

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

  function cancel() {
    const ch = activeChannel.value
    if (!ch.ws || ch.ws.readyState !== WebSocket.OPEN) return
    const payload: ClientMessage = { type: 'cancel', payload: {} }
    ch.ws.send(JSON.stringify(payload))
  }

  function sendUserResponse(interactionId: string, response: string | string[]) {
    const ch = activeChannel.value
    if (!ch.ws || ch.ws.readyState !== WebSocket.OPEN) return
    // 标记对应 ToolCall 的 interaction 为已提交，便于 findBestMatchingTool 后续精确匹配
    const turn = ch.currentTurn
    if (turn) {
      for (const ev of turn.events) {
        if (ev.kind === 'tool' && ev.interaction?.interactionId === interactionId) {
          ev.interaction.submitted = true
          break
        }
      }
    }
    const payload: ClientMessage = {
      type: 'user_response',
      payload: { interaction_id: interactionId, response },
    }
    ch.ws.send(JSON.stringify(payload))
  }

  /** 从当前会话的 turns 列表中移除最后 count 条轮次（撤回后的前端同步）。 */
  function removeTurns(count: number) {
    const ch = getOrCreateChannel(sessionId.value)
    if (ch.turns.length === 0) return
    const actual = Math.min(count, ch.turns.length)
    ch.turns.splice(ch.turns.length - actual, actual)
    if (!ch.privateMode) {
      persistTurns(sessionId.value)
    }
    void refreshSessions()
  }

  return {
    connected, isStreaming, turns, currentTurn, error, contextUsage, taskTrackerData,
    send, cancel, sendUserResponse, removeTurns,
    privateMode, setPrivateMode,
    autoApprove, setAutoApprove,
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

/**
 * 通过 call_id 精确查找 ToolCall（当多个同名工具并行运行时用于精准匹配）。
 */
function findToolByCallId(events: TurnEvent[], callId: string): ToolCall | undefined {
  for (const e of events) {
    if (e.kind === 'tool' && e.callId === callId) {
      return e as ToolCall
    }
  }
  return undefined
}

/**
 * 为 ask_user 事件查找合适的 ToolCall：
 * 从前往后找第一个 running 且尚未分配 interaction 的工具。
 * 当多个同名工具并行运行时，确保每个 ask_user 事件绑定到正确的实例。
 */
function findFirstRunningToolForInteraction(events: TurnEvent[], toolName: string): ToolCall | undefined {
  for (let i = 0; i < events.length; i++) {
    const e = events[i]
    if (e.kind === 'tool' && e.name === toolName && e.status === 'running' && !e.interaction) {
      return e as ToolCall
    }
  }
  return undefined
}

/**
 * 降级匹配：为 tool_end / tool_error 查找匹配的 ToolCall（当 call_id 匹配失败时使用）。
 * 1. 优先找 interaction.submitted === true 的工具（用户已响应）
 * 2. 其次找有 interaction 的工具
 * 3. 最后退化为旧行为：从后往前找最后一个 running 的工具
 */
function findBestMatchingTool(events: TurnEvent[], toolName: string): ToolCall | undefined {
  // 第一遍：优先匹配用户已提交响应的工具
  for (let i = 0; i < events.length; i++) {
    const e = events[i]
    if (e.kind === 'tool' && e.name === toolName && e.status === 'running' && e.interaction?.submitted) {
      return e as ToolCall
    }
  }
  // 第二遍：匹配有 interaction 的工具（未标记 submitted，可能不完美，但比旧行为好）
  for (let i = 0; i < events.length; i++) {
    const e = events[i]
    if (e.kind === 'tool' && e.name === toolName && e.status === 'running' && e.interaction) {
      return e as ToolCall
    }
  }
  // 第三遍（降级）：旧行为——最后一个 running 的同名工具
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i]
    if (e.kind === 'tool' && e.name === toolName && e.status === 'running') {
      return e as ToolCall
    }
  }
  return undefined
}

/** 通过后端 turn_id 查找 turn（先在 currentTurn 中找，再在 turns 中找）。 */
function findTurnByBackendId(ch: SessionChannel, turnId: string): ChatTurn | undefined {
  if (ch.currentTurn?.turnId === turnId) return ch.currentTurn
  return ch.turns.find(t => t.turnId === turnId)
}

/** 在 memoryEvents 中查找指定工具名的 running 状态事件。 */
function findRunningMemoryTool(events: MemoryToolEvent[], toolName: string): MemoryToolEvent | undefined {
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i]
    if (e.name === toolName && e.status === 'running') return e
  }
  return undefined
}
