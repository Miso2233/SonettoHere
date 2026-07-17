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
  const autoApprove = computed(() => activeChannelRef.value.autoApprove)

  function setPrivateMode(val: boolean) {
    const ch = activeChannelRef.value
    ch.privateMode = val
  }

  function setAutoApprove(val: boolean) {
    store.updateAutoApprove(sessionId.value, val)
  }

  // Session 切换：持久化旧会话、恢复新会话缓存、确保 WS 连接
  // getOrCreateChannel 在 store 内部已自动从 localStorage 恢复缓存
  watch(
    sessionId,
    (newId, oldId) => {
      if (oldId) store.persistTurns(oldId)
      store.ensureConnected(newId)
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
    autoApprove, setAutoApprove,
  }
}
