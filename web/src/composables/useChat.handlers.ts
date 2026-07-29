import { nextTick } from 'vue'
import type { SessionChannel } from '@/stores/chatStore'
import { findLastThinking, findToolByCallId, findBestMatchingTool, findFirstRunningToolForInteraction } from '@/stores/chatStore'
import { useChatStore } from '@/stores/chatStore'
import { useSessionStore } from '@/stores/sessionStore'
import type { ServerEvent, ChatTurn, TokenEvent, AnswerEvent, ErrorEvent, DoneEvent, AskUserEvent } from '@/types'

/** 事件路由处理器签名（turn 已由调用方守卫保证存在）。 */
type TurnEventHandler = (ch: SessionChannel, sid: string, turn: ChatTurn, event: ServerEvent) => void

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

  // ── 防重复守卫：若 turn 已存在于 turns 中则跳过 ──
  if (ch.turns.some(t => t.id === turn.id)) {
    console.warn(`[useChat:done] 防重复守卫触发: 会话 ${sid}, turn.id=${turn.id} 已在 turns 中, 跳过 push`)
    ch.currentTurn = null
    ch.isStreaming = false
    return
  }

  const lastThink = findLastThinking(turn.events)
  const trackBecame = lastThink?.becameAnswer
  console.log(`[useChat:done] 会话 ${sid}: becameAnswer=${trackBecame}, events=${turn.events.length}, finalAnswer=${turn.finalAnswer?.slice(0, 50) ?? 'null'}`)
  if (trackBecame) {
    const turnToFinalize = turn
    void nextTick(() => {
      setTimeout(() => {
        console.log(`[useChat:done] becameAnswer 分支执行 persist (会话 ${sid})`)
        // 延迟后再检查一次：turns 中可能已被其他逻辑写入
        if (ch.turns.some(t => t.id === turnToFinalize.id)) {
          console.warn(`[useChat:done] becameAnswer 防重复守卫触发: 会话 ${sid}, turn.id=${turnToFinalize.id}`)
          ch.currentTurn = null
          ch.isStreaming = false
          return
        }
        ch.turns.push(turnToFinalize)
        ch.currentTurn = null
        ch.isStreaming = false
        if (!ch.privateMode) { useChatStore().persistTurns(sid) }
      }, 420)
    })
  } else {
    console.log(`[useChat:done] 直接分支执行 persist (会话 ${sid}), turns.length=${ch.turns.length}`)
    ch.turns.push(turn)
    ch.currentTurn = null
    ch.isStreaming = false
    if (!ch.privateMode) { useChatStore().persistTurns(sid) }
  }
  // 轮次结束，刷新会话列表以更新 message_count
  void useSessionStore().refreshSessions()
  // 子 Agent 完成 → 自动切回主会话
  if (ch.parentSessionId) {
    setTimeout(() => useSessionStore().switchSession(ch.parentSessionId!), 500)
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

/** 事件路由处理器注册表。 */
export const turnHandlers = new Map<string, TurnEventHandler>([
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
