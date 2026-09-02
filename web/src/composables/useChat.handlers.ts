import { nextTick } from 'vue'
import type { SessionChannel } from '@/stores/chatStore'
import { findLastThinking, findToolByCallId, findBestMatchingTool, findFirstRunningToolForInteraction } from '@/stores/chatStore'
import { useChatStore } from '@/stores/chatStore'
import { useSessionStore } from '@/stores/sessionStore'
import type { ServerEvent, ChatTurn, TokenEvent, ThinkingTokenEvent, AnswerEvent, ErrorEvent, DoneEvent, AskUserEvent, ToolStreamEvent } from '@/types'

/** 事件路由处理器签名（turn 已由调用方守卫保证存在）。 */
type TurnEventHandler = (ch: SessionChannel, sid: string, turn: ChatTurn, event: ServerEvent) => void

/**
 * 从块式 token 中提取纯文本（与后端 websocket_callback._extract_block_token 对应）。
 *
 * 部分 Anthropic 适配模型（如 Kimi K3）把流式 content blocks 透传为 token：
 * JSON 字符串（如 `[{"type":"thinking","thinking":"用","index":0}]`）或数组。
 * 这里解析并提取 text 块正文（`type:"text"`）与 thinking 块正文（`type:"thinking"`）。
 *
 * @returns `{ text, thinking }` — 两者都为空表示 token 不是块式结构。
 */
function extractBlockToken(token: unknown): { text: string; thinking: string } {
  let blocks: unknown[] | null = null
  if (Array.isArray(token)) {
    blocks = token
  } else if (typeof token === 'string' && token.trimStart().startsWith('[')) {
    try {
      const parsed = JSON.parse(token) as unknown
      if (Array.isArray(parsed)) {
        blocks = parsed
      } else if (typeof parsed === 'string') {
        // JSON 字符串字面量（如 `"hello"`）当作普通文本
        return { text: parsed, thinking: '' }
      } else {
        return { text: '', thinking: '' }
      }
    } catch {
      return { text: '', thinking: '' }
    }
  }
  if (!blocks) return { text: '', thinking: '' }

  let text = ''
  let thinking = ''
  for (const block of blocks) {
    if (!block || typeof block !== 'object') continue
    const b = block as { type?: unknown; text?: unknown; thinking?: unknown }
    if (b.type === 'text' && typeof b.text === 'string') {
      text += b.text
    } else if (b.type === 'thinking' && typeof b.thinking === 'string') {
      thinking += b.thinking
    }
  }
  return { text, thinking }
}

/** thinking_start：压入思考块。 */
function handleThinkingStart(ch: SessionChannel, _sid: string, turn: ChatTurn, _event: ServerEvent): void {
  // 调试：确认流式思考块何时创建（排查是否有 token 在 thinking 块之前到达）
  console.log('[useChat:thinking_start] 创建思考块, turn.events.length=', turn.events.length)
  turn.events.push({ kind: 'thinking', thinkingCount: 0, tokens: '', done: false, becameAnswer: false })
}

/** thinking_token：更新最后一个思考块的思考进度计数。 */
function handleThinkingToken(ch: SessionChannel, _sid: string, turn: ChatTurn, event: ServerEvent): void {
  const lastThink = findLastThinking(turn.events)
  const count = (event as ThinkingTokenEvent).payload.count
  // 调试：确认 thinking 计数到达（用于排查空 token chunk 计数是否正常触发）
  if (typeof count !== 'number' || count % 10 === 0) {
    console.log('[useChat:thinking_token] count=', count, 'typeof=', typeof count, 'hasThinkingBlock=', !!lastThink)
  }
  if (lastThink) {
    lastThink.thinkingCount = count
  }
}

/** token：追加正文到最后一个思考块。 */
function handleToken(ch: SessionChannel, _sid: string, turn: ChatTurn, event: ServerEvent): void {
  const rawToken = (event as TokenEvent).payload.token
  const lastThink = findLastThinking(turn.events)
  // 调试：定位 [object Object] 来源——payload.token 必须是字符串。
  // 若 typeof 不是 string，说明后端把结构化对象（如 content blocks 数组）当作 token 推送。
  if (typeof rawToken !== 'string' || rawToken === '[object Object]') {
    let serialized: string
    try {
      serialized = JSON.stringify(rawToken)
    } catch {
      serialized = `[unserializable:${typeof rawToken}]`
    }
    console.warn('[useChat:token] ⚠️ token 非字符串！typeof=', typeof rawToken, 'value=', serialized?.slice(0, 300), 'hasThinkingBlock=', !!lastThink)
  }
  // 归一化块式 token（Kimi K3 等 Anthropic 适配模型）：提取 text 块正文，
  // thinking 块正文不展示（与后端"不展示思考明文"策略一致）。
  const { text: blockText } = extractBlockToken(rawToken)
  const token = blockText !== ''
    ? blockText
    : (typeof rawToken === 'string' ? rawToken : '')
  if (lastThink && token) {
    lastThink.tokens += token
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

/** tool_stream：把实时输出片段追加到匹配工具调用的 stream 缓冲。 */
function handleToolStream(ch: SessionChannel, _sid: string, turn: ChatTurn, event: ServerEvent): void {
  const tsEvent = event as ToolStreamEvent
  // 精确匹配优先（call_id 与 tool_start/end 一致），缺省再按 tool_name 兜底，
  // 与 tool_end / tool_error 的匹配策略保持一致。
  const tc = findToolByCallId(turn.events, tsEvent.payload.call_id)
    ?? findBestMatchingTool(turn.events, tsEvent.payload.tool_name)
  if (tc) {
    tc.stream = (tc.stream ?? '') + tsEvent.payload.chunk
  }
}

/** answer：标记思考块为 becameAnswer，设置 finalAnswer。 */
function handleAnswer(ch: SessionChannel, _sid: string, turn: ChatTurn, event: ServerEvent): void {
  const content = (event as AnswerEvent).payload.content
  // 调试：answer 必须是字符串，否则 MessageBubble 会渲染 [object Object]
  if (typeof content !== 'string') {
    let serialized: string
    try {
      serialized = JSON.stringify(content)
    } catch {
      serialized = `[unserializable:${typeof content}]`
    }
    console.warn('[useChat:answer] ⚠️ content 非字符串！typeof=', typeof content, 'value=', serialized?.slice(0, 500))
  }
  const lastThink = findLastThinking(turn.events)
  if (lastThink) {
    lastThink.becameAnswer = true
  }
  turn.finalAnswer = typeof content === 'string' ? content : (() => {
    try { return JSON.stringify(content) } catch { return String(content) }
  })()
}

/** done：finalize 当前轮次，持久化，刷新会话列表。 */
function handleDone(ch: SessionChannel, sid: string, turn: ChatTurn, event: ServerEvent): void {
  const de = event as DoneEvent
  ch.isAwaitingUser = false
  ch._awaitingToolName = null
  // 注：工具间隙注入的消息已由 pending_consumed(mid_turn) 移入聊天流渲染
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
    if (ch.currentTurn?.id === turn.id) {
      ch.currentTurn = null
      ch.isStreaming = false
    }
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
          if (ch.currentTurn?.id === turnToFinalize.id) {
            ch.currentTurn = null
            ch.isStreaming = false
          }
          return
        }
        ch.turns.push(turnToFinalize)
        // ⚠ id 守卫：420ms 延迟窗口内可能已由 pending_consumed(new_turn)
        // 创建了下一合并轮，不得清空它
        if (ch.currentTurn?.id === turnToFinalize.id) {
          ch.currentTurn = null
          ch.isStreaming = false
        }
        if (!ch.privateMode) { useChatStore().persistTurns(sid) }
      }, 420)
    })
  } else {
    console.log(`[useChat:done] 直接分支执行 persist (会话 ${sid}), turns.length=${ch.turns.length}`)
    ch.turns.push(turn)
    if (ch.currentTurn?.id === turn.id) {
      ch.currentTurn = null
      ch.isStreaming = false
    }
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
  // 用户点击停止（CANCELLED）→ 排队消息一并丢弃，与后端 pending_cancelled 语义一致
  if ((event as ErrorEvent).payload.code === 'CANCELLED') {
    ch.pendingMessages = []
  }
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
    // code 顶层保留（PythonBubble/ConfirmBubble 兼容）；其余载荷并入 payload
    // 供 ConfirmBubble 渲染文件工具的路径/内容/编辑等确认信息。
    const { tool_name, question, mode, options, interaction_id, code, ...extra } = ae.payload
    runningTool.interaction = {
      question,
      mode,
      options,
      interactionId: interaction_id,
      submitted: false,
      code,
      payload: Object.keys(extra).length > 0 ? extra : undefined,
    }
  }
}

/** 事件路由处理器注册表。 */
export const turnHandlers = new Map<string, TurnEventHandler>([
  ['thinking_start', handleThinkingStart],
  ['thinking_token', handleThinkingToken],
  ['token', handleToken],
  ['thinking_end', handleThinkingEnd],
  ['tool_start', handleToolStart],
  ['tool_end', handleToolEnd],
  ['tool_error', handleToolError],
  ['tool_stream', handleToolStream],
  ['answer', handleAnswer],
  ['done', handleDone],
  ['error', handleError],
  ['ask_user', handleAskUser],
])
