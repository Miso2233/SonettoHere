import { reactive, computed, watch, nextTick, type Ref } from 'vue'
import type { ClientMessage, ServerEvent, ChatTurn, ToolCall, ThinkingBlock, TurnEvent, ContextUsage, AskUserEvent } from '@/types'
import { refreshSessions, switchSession } from '@/composables/useSession'

export const TURNS_KEY_PREFIX = 'sonetto_turns_'

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
          console.log(`[useChat:load] 从 localStorage 加载会话 ${sid}: ${data.length} 条 turn, 序列化长度 ${raw.length}`)
          map.set(sid, data)
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
  reconnectTimer: ReturnType<typeof setTimeout> | null
  initialized: boolean
  _awaitingToolName: string | null
  parentSessionId: string | null  // sub-agent 用：完成时切回主会话
  privateMode: boolean
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
      reconnectTimer: null,
      initialized: false,
      _awaitingToolName: null,
      parentSessionId: null,
      privateMode: false,
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

export function ensureConnected(sid: string) {
  if (!sid) {
    console.warn(`[useChat:ensureConnected] 跳过空 sid`)
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
      events: [],
      finalAnswer: null,
    }

    void switchSession(subId)
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
      // ask_user 工具执行完毕 → 用户已回应，回到工作态
      if (ch.isAwaitingUser && event.payload.tool_name === ch._awaitingToolName) {
        ch.isAwaitingUser = false
        ch._awaitingToolName = null
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
      ch.isAwaitingUser = false
      ch._awaitingToolName = null
      if (event.payload.context_usage) {
        ch.contextUsage = event.payload.context_usage
      }
      if (ch.currentTurn) {
        const lastThink = findLastThinking(ch.currentTurn.events)
        const trackBecame = lastThink?.becameAnswer
        console.log(`[useChat:done] 会话 ${sid}: becameAnswer=${trackBecame}, events=${ch.currentTurn.events.length}, finalAnswer=${ch.currentTurn.finalAnswer?.slice(0, 50) ?? 'null'}`)
        if (trackBecame) {
          const turnToFinalize = ch.currentTurn
          void nextTick(() => {
            setTimeout(() => {
              console.log(`[useChat:done] becameAnswer 分支执行 persist (会话 ${sid})`)
              ch.turns.push(turnToFinalize)
              ch.currentTurn = null
              ch.isStreaming = false
              if (!ch.privateMode) {
                persistTurns(sid)
              }
            }, 420)
          })
        } else {
          console.log(`[useChat:done] 直接分支执行 persist (会话 ${sid})`)
          ch.turns.push(ch.currentTurn)
          ch.currentTurn = null
          ch.isStreaming = false
          if (!ch.privateMode) {
            persistTurns(sid)
          }
        }
        void refreshSessions()  // 轮次结束，刷新会话列表以更新 message_count
      } else {
        console.warn(`[useChat:done] 会话 ${sid} 的 done 事件到达时 currentTurn 为 null`)
        ch.isStreaming = false
      }
      // 子 Agent 完成 → 自动切回主会话
      if (ch.parentSessionId) {
        setTimeout(() => switchSession(ch.parentSessionId!), 500)
      }
      break

    case 'error':
      ch.isAwaitingUser = false
      ch._awaitingToolName = null
      ch.error = event.payload.message
      ch.isStreaming = false
      break

    case 'pong':
      break

    case 'ask_user': {
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

  const privateMode = computed(() => activeChannel.value.privateMode)

  function setPrivateMode(val: boolean) {
    activeChannel.value.privateMode = val
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

  function send(message: string, providerId?: string, modelName?: string) {
    const ch = activeChannel.value
    if (!ch.ws || ch.ws.readyState !== WebSocket.OPEN) {
      console.warn(`[useChat:send] WebSocket 未就绪, readyState=${ch.ws?.readyState}, session=${sessionId.value}`)
      return
    }
    console.log(`[useChat:send] 发送消息 (session=${sessionId.value}): "${message.slice(0, 80)}..."`)
    ch.isStreaming = true
    ch.error = null

    const turn: ChatTurn = {
      id: crypto.randomUUID(),
      userMessage: message,
      events: [],
      finalAnswer: null,
    }
    ch.currentTurn = turn

    const payload: ClientMessage = {
      type: 'chat',
      payload: { message, private: ch.privateMode, provider_id: providerId, model_name: modelName },
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
    connected, isStreaming, turns, currentTurn, error, contextUsage,
    send, cancel, sendUserResponse, removeTurns,
    privateMode, setPrivateMode,
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
