import type {
  CreateSessionResponse,
  ListSessionsResponse,
  SessionInfo,
  ContextUsage,
  ConstifyResponse,
} from '@/types'
import { request } from './client'

export const sessionsApi = {
  createSession: () =>
    request<CreateSessionResponse>('/sessions', { method: 'POST' }),

  listSessions: () =>
    request<ListSessionsResponse>('/sessions'),

  getSession: (id: string) =>
    request<SessionInfo>(`/sessions/${id}`),

  deleteSession: (id: string) =>
    request<{ status: string }>(`/sessions/${id}`, { method: 'DELETE' }),

  getContextUsage: (sessionId: string) =>
    request<ContextUsage & { session_id: string }>(`/sessions/${sessionId}/context-usage`),

  undoMessages: (sessionId: string, n: number = 1) =>
    request<{ deleted_count: number }>(`/sessions/${sessionId}/undo?n=${n}`, { method: 'POST' }),

  constifySession: (id: string, name: string) =>
    request<ConstifyResponse>(`/sessions/${id}/const`, {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),

  unconstifySession: (id: string) =>
    request<{ status: string }>(`/sessions/${id}/const`, { method: 'DELETE' }),

  generateSessionTitle: (id: string) =>
    request<{ title: string }>(`/sessions/${id}/generate-title`, { method: 'POST' }),
}