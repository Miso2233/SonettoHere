import type {
  CreateSessionResponse,
  ListSessionsResponse,
  SessionInfo,
  NarrativeResponse,
} from '@/types'

const BASE = '/api'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    throw new Error(`API ${url} 返回 ${res.status}`)
  }
  return res.json()
}

export const api = {
  createSession: () =>
    request<CreateSessionResponse>('/sessions', { method: 'POST' }),

  listSessions: () =>
    request<ListSessionsResponse>('/sessions'),

  getSession: (id: string) =>
    request<SessionInfo>(`/sessions/${id}`),

  deleteSession: (id: string) =>
    request<{ status: string }>(`/sessions/${id}`, { method: 'DELETE' }),

  getNarrative: () =>
    request<NarrativeResponse>('/narrative'),
}
