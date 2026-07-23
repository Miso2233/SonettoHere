import type {
  CreateSessionResponse,
  ListSessionsResponse,
  SessionInfo,
  ContextUsage,
  ConstifyResponse,
} from '@/types'
import { request } from './client'

export const sessionsApi = {
  // ── 会话生命周期 ──

  /** 创建新会话 */
  createSession: () =>
    request<CreateSessionResponse>('/sessions', { method: 'POST' }),

  /** 获取所有会话列表 */
  listSessions: () =>
    request<ListSessionsResponse>('/sessions'),

  /** 获取指定会话信息 */
  getSession: (id: string) =>
    request<SessionInfo>(`/sessions/${id}`),

  /**
   * 删除指定会话及其所有消息
   * @param id - 会话 ID
   */
  deleteSession: (id: string) =>
    request<{ status: string }>(`/sessions/${id}`, { method: 'DELETE' }),

  // ── 会话控制 ──

  /**
   * 获取指定会话的上下文窗口用量
   * @param sessionId - 会话 ID
   */
  getContextUsage: (sessionId: string) =>
    request<ContextUsage & { session_id: string }>(`/sessions/${sessionId}/context-usage`),

  /**
   * 撤销指定会话最近 n 条消息
   * @param sessionId - 会话 ID
   * @param n - 撤销条数，默认 1
   * @returns 实际删除的消息数量
   */
  undoMessages: (sessionId: string, n: number = 1) =>
    request<{ deleted_count: number }>(`/sessions/${sessionId}/undo?n=${n}`, { method: 'POST' }),

  /**
   * 将会话设为固定（const），固定在侧边栏顶部不被自动清理
   * @param id - 会话 ID
   * @param name - 固定后显示的名称
   */
  constifySession: (id: string, name: string) =>
    request<ConstifyResponse>(`/sessions/${id}/const`, {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),

  /** 取消会话固定 */
  unconstifySession: (id: string) =>
    request<{ status: string }>(`/sessions/${id}/const`, { method: 'DELETE' }),

  /**
   * 让 AI 根据会话内容自动生成标题
   * @param id - 会话 ID
   * @returns 生成的标题
   */
  generateSessionTitle: (id: string) =>
    request<{ title: string }>(`/sessions/${id}/generate-title`, { method: 'POST' }),
}
