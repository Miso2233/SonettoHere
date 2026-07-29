import { computed, watch, type Ref } from 'vue'
import { useChatStore, findLastThinking, findToolByCallId, findBestMatchingTool, findFirstRunningToolForInteraction, findTurnByBackendId, findRunningMemoryTool } from '@/stores/chatStore'
import type { ParsedRef } from '@/utils/references'

// 向后兼容导出
export { findLastThinking, findToolByCallId, findBestMatchingTool, findFirstRunningToolForInteraction, findTurnByBackendId, findRunningMemoryTool }
export const TURNS_KEY_PREFIX = 'sonetto_turns_'

/** @deprecated 使用 useChatStore().disconnectChannel() */
export function disconnectSession(sid: string) {
  useChatStore().disconnectChannel(sid)
}

/** @deprecated 使用 useChatStore().removeTurnsFromStorage() */
export function removeTurnsFromStorage(sid: string) {
  useChatStore().removeTurnsFromStorage(sid)
}

/** @deprecated 使用 useChatStore().persistTurns() */
export function persistTurns(sid: string) {
  useChatStore().persistTurns(sid)
}

/** @deprecated 使用 useChatStore().allSessionStatuses */
export const allSessionStatuses = computed(() => useChatStore().allSessionStatuses)

/**
 * useChat composable — 委托到 Pinia store。
 *
 * 保持现有 API 接口不变：
 *   connected, isStreaming, turns, currentTurn, error,
 *   contextUsage, taskTrackerData, send, cancel, sendUserResponse, removeTurns,
 *   privateMode, setPrivateMode, autoApprove, setAutoApprove
 */
export function useChat(sessionId: Ref<string>) {
  const store = useChatStore()

  // 根据当前 sessionId 获取通道状态
  const activeChannelRef = computed(() => store.getOrCreateChannel(sessionId.value))

  const connected = computed(() => activeChannelRef.value.connected)
  const isStreaming = computed(() => activeChannelRef.value.isStreaming)
  const turns = computed(() => activeChannelRef.value.turns)
  const currentTurn = computed(() => activeChannelRef.value.currentTurn)
  const error = computed(() => activeChannelRef.value.error)
  const contextUsage = computed(() => activeChannelRef.value.contextUsage)
  const taskTrackerData = computed(() => activeChannelRef.value.taskTrackerData)
  const privateMode = computed(() => activeChannelRef.value.privateMode)
  const skipRecall = computed(() => activeChannelRef.value.skipRecall)
  const autoApprove = computed(() => activeChannelRef.value.autoApprove)

  function setPrivateMode(val: boolean) {
    const ch = activeChannelRef.value
    ch.privateMode = val
  }

  function setSkipRecall(val: boolean) {
    const ch = activeChannelRef.value
    ch.skipRecall = val
  }

  function setAutoApprove(val: boolean) {
    store.updateAutoApprove(sessionId.value, val)
  }

  // Session 切换：持久化旧会话、恢复新会话缓存（优先 localStorage, 其次后端）、确保 WS 连接
  watch(
    sessionId,
    async (newId, oldId) => {
      console.warn('[useChat] ⚡ watch(sessionId): old=%s, new=%s', oldId, newId)
      if (oldId) {
        console.warn('[useChat] 持久化旧会话: %s', oldId)
        store.persistTurns(oldId)
      }
      console.warn('[useChat] 确保新会话连接: %s', newId)
      store.ensureConnected(newId)
      // 若 localStorage 无缓存, 从后端拉取历史消息恢复
      const ch = store.getOrCreateChannel(newId)
      console.warn('[useChat] 新会话通道 turns.length=%d, currentTurn=%s', ch.turns.length, ch.currentTurn?.id ?? 'null')
      // 若 turns 为空且无 currentTurn（无正在流式的轮次），才从后端恢复历史消息；
      // 反之若存在 currentTurn，说明该通道有未完成的轮次，会话仍是「活的」，恢复会导致后端消息与 currentTurn 同时出现
      if (ch.turns.length === 0 && !ch.currentTurn) {
        console.warn('[useChat] 本地无缓存且无活动轮次, 尝试从后端恢复历史消息: %s', newId)
        await store.restoreTurnsFromBackend(newId)
        console.warn('[useChat] 后端恢复完成: session=%s, turns.length=%d', newId, ch.turns.length)
      }
    },
    { immediate: true },
  )

  function send(text: string, refs: ParsedRef[] = [], providerId?: string, modelName?: string, imageRecognition?: boolean, imagePaths?: string[]) {
    store.send(sessionId.value, text, refs, providerId, modelName, imageRecognition, imagePaths)
  }

  function cancel() {
    store.cancel(sessionId.value)
  }

  function sendUserResponse(interactionId: string, response: string | string[]) {
    store.sendUserResponse(sessionId.value, interactionId, response)
  }

  function removeTurns(count: number) {
    store.removeTurns(sessionId.value, count)
  }

  return {
    connected, isStreaming, turns, currentTurn, error, contextUsage, taskTrackerData,
    send, cancel, sendUserResponse, removeTurns,
    privateMode, setPrivateMode,
    skipRecall, setSkipRecall,
    autoApprove, setAutoApprove,
  }
}
