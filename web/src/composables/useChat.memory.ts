import type { SessionChannel } from '@/stores/chatStore'
import { findTurnByBackendId, findRunningMemoryTool, findMemoryReview, findReviewTurn } from '@/stores/chatStore'
import { useChatStore } from '@/stores/chatStore'
import type { ServerEvent, MemoryStartEvent, MemoryToolStartEvent, MemoryToolEndEvent, MemoryToolErrorEvent, MemoryDoneEvent, MemoryReviewRequiredEvent, MemoryReviewResultEvent, MemoryToolEvent, ChatTurn } from '@/types'

/** read_memories 是纯读取操作，前端无需显示其执行状态。 */
function skipReadMemories(payload: { tool_name: string }): boolean {
  return payload.tool_name === 'read_memories'
}

/** 诊断用：该会话当前已知的全部 turn_id。事件定位失败时才能看出错配在哪。 */
function knownTurnIds(ch: SessionChannel): string {
  const archived = ch.turns.map(t => t.turnId || '(未设置)').join(', ')
  const current = ch.currentTurn ? (ch.currentTurn.turnId || '(未设置)') : '(无currentTurn)'
  return `currentTurn=${current} 已归档=[${archived}]`
}

/**
 * 早到的 memory_start 暂存区：session_id → 待补占位条目的 turn_id 集合。
 *
 * 前端靠 `done` 事件才拿到 turn_id，而 `ltm_write` 入队即返回——后台 consumer
 * 完全可能抢在 `done` 之前把 memory_start 推过来，此时没有任何轮次可匹配。
 * 直接丢弃会让整轮失去「处理中」反馈，故先记下意图，等该轮次可定位时补压。
 */
const pendingStarts = new Map<string, Set<string>>()

function rememberPendingStart(sid: string, turnId: string): void {
  const set = pendingStarts.get(sid) ?? new Set<string>()
  set.add(turnId)
  pendingStarts.set(sid, set)
}

function forgetPendingStart(sid: string, turnId: string): void {
  const set = pendingStarts.get(sid)
  if (!set) return
  set.delete(turnId)
  if (set.size === 0) pendingStarts.delete(sid)
}

/** 压入「处理中」占位条目。 */
function pushProcessingPlaceholder(turn: ChatTurn): void {
  if (!turn.memoryEvents) turn.memoryEvents = []
  turn.memoryEvents.push({
    kind: 'memory_tool', name: 'memory_processing', input: '', output: null, elapsed: null, status: 'running',
  })
}

/** 该轮次现已可定位：补上早到的 memory_start 占位条目。 */
function flushPendingStart(sid: string, turnId: string, turn: ChatTurn): void {
  const set = pendingStarts.get(sid)
  if (!set?.has(turnId)) return
  forgetPendingStart(sid, turnId)
  pushProcessingPlaceholder(turn)
}

/**
 * 后台记忆 consumer 事件类型。
 *
 * 注意 `memory_review_required` / `memory_review_result` 与 `memory_review`
 * 不是一回事：后者是 MemoryToolEvent.name 的取值，两者别混。
 */
export type MemoryEventType = 'memory_start' | 'memory_tool_start' | 'memory_tool_end' | 'memory_tool_error' | 'memory_done' | 'memory_review_required' | 'memory_review_result'

/** 后台记忆 consumer 事件处理器签名。 */
type MemoryEventHandler = (ch: SessionChannel, sid: string, event: ServerEvent) => void

/** 后台记忆 consumer 开始处理本轮对话：压入「处理中」占位条目。 */
function handleMemoryStart(ch: SessionChannel, sid: string, event: ServerEvent): void {
  const me = event as MemoryStartEvent
  console.log(`[ltm-fe] memory_start session=${sid} turn_id=${me.payload.turn_id}`)
  const targetTurn = findTurnByBackendId(ch, me.payload.turn_id)
  if (!targetTurn) {
    // 事件先于 `done` 到达（turn_id 尚未落到轮次上）——记下意图，等轮次可定位时补压。
    rememberPendingStart(sid, me.payload.turn_id)
    return
  }
  pushProcessingPlaceholder(targetTurn)
}

/** 后台记忆 consumer 开始调用 CRUD 工具：压入 running 状态工具事件。 */
function handleMemoryToolStart(ch: SessionChannel, sid: string, event: ServerEvent): void {
  const me = event as MemoryToolStartEvent
  if (skipReadMemories(me.payload)) return
  console.log(`[ltm-fe] memory_tool_start session=${sid} turn_id=${me.payload.turn_id} tool=${me.payload.tool_name}`)
  const targetTurn = findTurnByBackendId(ch, me.payload.turn_id)
  if (!targetTurn) {
    console.warn(
      `[ltm-fe] memory_tool_start 找不到所属轮次 turn_id=${me.payload.turn_id} ${knownTurnIds(ch)}`,
    )
    return
  }
  flushPendingStart(sid, me.payload.turn_id, targetTurn)
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
  if (!targetTurn) {
    console.warn(
      `[ltm-fe] memory_tool_end 找不到所属轮次 turn_id=${me.payload.turn_id} ${knownTurnIds(ch)}`,
    )
    return
  }
  const mt = findRunningMemoryTool(targetTurn.memoryEvents ?? [], me.payload.tool_name)
  if (mt) {
    mt.output = me.payload.output
    mt.elapsed = me.payload.elapsed
    mt.status = 'done'
  } else {
    // 没有在跑的对应条目：start 事件曾丢失，这条收尾无处落地。
    // 真正的兜底在 handleMemoryDone（收尾时统一清理 running），此处只留痕。
    console.warn(
      `[ltm-fe] memory_tool_end 无匹配的 running 条目 tool=${me.payload.tool_name} turn_id=${me.payload.turn_id}`,
    )
  }
  if (ch.turns.includes(targetTurn as ChatTurn)) useChatStore().persistTurns(sid)
}

/** 后台记忆 consumer 的 CRUD 工具出错：更新匹配事件为 error。 */
function handleMemoryToolError(ch: SessionChannel, sid: string, event: ServerEvent): void {
  const me = event as MemoryToolErrorEvent
  if (skipReadMemories(me.payload)) return
  const targetTurn = findTurnByBackendId(ch, me.payload.turn_id)
  if (!targetTurn) return
  const mt = findRunningMemoryTool(targetTurn.memoryEvents ?? [], me.payload.tool_name)
  if (mt) mt.status = 'error'
  if (ch.turns.includes(targetTurn as ChatTurn)) useChatStore().persistTurns(sid)
}

/** 后台记忆 consumer 处理完毕：移除「处理中」占位，无实际工具事件时渲染 memory_review。 */
function handleMemoryDone(ch: SessionChannel, sid: string, event: ServerEvent): void {
  const me = event as MemoryDoneEvent
  console.log(`[ltm-fe] memory_done session=${sid} turn_id=${me.payload.turn_id}`)
  // 本轮已结束，占位意图作废：即便此刻轮次还定位不到，
  // 也不该在稍后补压一个永远无人清理的「处理中」。
  forgetPendingStart(sid, me.payload.turn_id)
  const targetTurn = findTurnByBackendId(ch, me.payload.turn_id)
  if (!targetTurn) {
    console.warn(
      `[ltm-fe] memory_done 找不到所属轮次，该轮将停留在「处理中」turn_id=${me.payload.turn_id} ${knownTurnIds(ch)}`,
    )
    return
  }
  // 移除「处理中」占位条目，并把仍停在 running 的工具事件一并收尾。
  // consumer 已经跑完，非占位的 running 都只意味它那条 end 事件丢了；
  // 不清理的话 getMemorySummary 会永久返回 processing，图标永不停止。
  const realEvents = (targetTurn.memoryEvents ?? []).filter(e => e.name !== 'memory_processing')
  const stray = realEvents.filter(e => e.status === 'running')
  for (const e of stray) e.status = 'done'
  targetTurn.memoryEvents = realEvents
  if (stray.length > 0) {
    console.warn(
      `[ltm-fe] memory_done 收尾了 ${stray.length} 条残留 running 事件 turn_id=${me.payload.turn_id}：` +
      stray.map(e => e.name).join(', '),
    )
  }
  if (realEvents.length === 0) {
    targetTurn.memoryEvents = [{
      kind: 'memory_tool', name: 'memory_review', input: '', output: '', elapsed: null, status: 'done',
    }]
    console.log(`[ltm-fe] added memory_review`)
  }
  if (ch.turns.includes(targetTurn as ChatTurn)) useChatStore().persistTurns(sid)
}

/**
 * 后台记忆写入 TECH/PROJECT/MOMENT：在轮次上挂一张待处理复核卡片。
 *
 * 卡片渲染在 callback 小图标（memory-tool-log）正下方。
 */
function handleMemoryReviewRequired(ch: SessionChannel, sid: string, event: ServerEvent): void {
  const me = event as MemoryReviewRequiredEvent
  const targetTurn = findTurnByBackendId(ch, me.payload.turn_id)
  if (!targetTurn) {
    console.warn(
      `[ltm-fe] memory_review_required 找不到所属轮次，卡片将不显示 ` +
      `review_id=${me.payload.review_id} turn_id=${me.payload.turn_id} ${knownTurnIds(ch)}`,
    )
    return
  }
  flushPendingStart(sid, me.payload.turn_id, targetTurn)
  const reviews = (targetTurn.memoryReviews ??= [])
  // WS 重连时后端会补推未决复核，按 review_id 去重避免重复卡片
  if (reviews.some(r => r.reviewId === me.payload.review_id)) return
  reviews.push({
    reviewId: me.payload.review_id,
    kind: me.payload.kind,
    memoryId: me.payload.memory_id,
    description: me.payload.description,
    theme: me.payload.theme,
    themeLabel: me.payload.theme_label,
    status: 'pending',
    submitting: false,
    detail: '',
  })
  console.log(`[ltm-fe] memory_review_required session=${sid} review=${me.payload.review_id} theme=${me.payload.theme}`)
  if (ch.turns.includes(targetTurn as ChatTurn)) useChatStore().persistTurns(sid)
}

/**
 * 把该次 create 对应的记忆工具事件标记为已撤销。
 *
 * 事件与复核之间没有显式 ID 关联：create_memory 的输出形如
 * `已创建 [xxxxxxxx] (TECH): 内容`，故用 `[memoryId]` 反查。
 * 只匹配 create_memory，避免误伤 output 里恰好提到同一 ID 的 link / merge 事件。
 */
function markCreateRevoked(turn: ChatTurn, memoryId: string): void {
  const marker = `[${memoryId}]`
  for (const e of turn.memoryEvents ?? []) {
    if (e.name === 'create_memory' && e.status === 'done' && e.output?.includes(marker)) {
      e.revoked = true
      return
    }
  }
  console.log(`[ltm-fe] NO create_memory event matched memory_id=${memoryId}`)
}

/** 复核决定回执：把卡片改成终态（已保留 / 已撤销 / 已失效 / 撤销失败）。 */
function handleMemoryReviewResult(ch: SessionChannel, sid: string, event: ServerEvent): void {
  const me = event as MemoryReviewResultEvent
  // 回执不带 turn_id，按 review_id 跨轮次定位
  const target = findMemoryReview(ch, me.payload.review_id)
  if (!target) { console.log(`[ltm-fe] NO review found for ${me.payload.review_id}`); return }
  target.status = me.payload.status
  target.detail = me.payload.detail
  target.submitting = false
  console.log(`[ltm-fe] memory_review_result review=${me.payload.review_id} status=${me.payload.status}`)

  const owner = findReviewTurn(ch, me.payload.review_id)
  if (owner && me.payload.status === 'rejected') markCreateRevoked(owner, target.memoryId)

  // 仅当卡片归属已归档轮次时才落盘（currentTurn 的快照不完整）
  if (owner && ch.turns.includes(owner)) useChatStore().persistTurns(sid)
}

/** 记忆事件处理器注册表。新增记忆事件类型只需在此注册，调用方守卫自动覆盖。 */
export const memoryHandlers = new Map<MemoryEventType, MemoryEventHandler>([
  ['memory_start', handleMemoryStart],
  ['memory_tool_start', handleMemoryToolStart],
  ['memory_tool_end', handleMemoryToolEnd],
  ['memory_tool_error', handleMemoryToolError],
  ['memory_done', handleMemoryDone],
  ['memory_review_required', handleMemoryReviewRequired],
  ['memory_review_result', handleMemoryReviewResult],
])
