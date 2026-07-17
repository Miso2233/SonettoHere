import type { SessionChannel } from '@/stores/chatStore'
import { findTurnByBackendId, findRunningMemoryTool } from '@/stores/chatStore'
import { useChatStore } from '@/stores/chatStore'
import type { ServerEvent, MemoryStartEvent, MemoryToolStartEvent, MemoryToolEndEvent, MemoryToolErrorEvent, MemoryDoneEvent, MemoryToolEvent, ChatTurn } from '@/types'

/** read_memories 是纯读取操作，前端无需显示其执行状态。 */
function skipReadMemories(payload: { tool_name: string }): boolean {
  return payload.tool_name === 'read_memories'
}

/** 后台记忆 consumer 事件类型。 */
export type MemoryEventType = 'memory_start' | 'memory_tool_start' | 'memory_tool_end' | 'memory_tool_error' | 'memory_done'

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

/** 记忆事件处理器注册表。新增记忆事件类型只需在此注册，调用方守卫自动覆盖。 */
export const memoryHandlers = new Map<MemoryEventType, MemoryEventHandler>([
  ['memory_start', handleMemoryStart],
  ['memory_tool_start', handleMemoryToolStart],
  ['memory_tool_end', handleMemoryToolEnd],
  ['memory_tool_error', handleMemoryToolError],
  ['memory_done', handleMemoryDone],
])
