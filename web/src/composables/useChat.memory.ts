import type { SessionChannel } from '@/stores/chatStore'
import { findTurnByBackendId, findRunningMemoryTool, findMemoryReview, findReviewTurn } from '@/stores/chatStore'
import { useChatStore } from '@/stores/chatStore'
import type { ServerEvent, MemoryStartEvent, MemoryToolStartEvent, MemoryToolEndEvent, MemoryToolErrorEvent, MemoryDoneEvent, MemoryReviewRequiredEvent, MemoryReviewResultEvent, MemoryToolEvent, ChatTurn } from '@/types'

/** read_memories 是纯读取操作，前端无需显示其执行状态。 */
function skipReadMemories(payload: { tool_name: string }): boolean {
  return payload.tool_name === 'read_memories'
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
  if (!targetTurn) { console.log(`[ltm-fe] NO turn found for review turn_id=${me.payload.turn_id}`); return }
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
