import type {
  CreateSessionResponse,
  ListSessionsResponse,
  SessionInfo,
  NarrativeResponse,
  MomentResponse,
  VignetteResponse,
  ContextUsage,
  DeepSeekBalanceResponse,
  HealthResponse,
  ListProvidersResponse,
  ListNewsResponse,
  ListSkillsResponse,
  ListToolsResponse,
  ProviderConfig,
  TestConnectionResponse,
  DiscoverModelsResponse,
  ConstifyResponse,
  WhitelistEntry,
  ListWhitelistResponse,
  BlockerEntry,
  ListBlockerResponse,
} from '@/types'

declare const __API_TOKEN__: string

const BASE = '/api'

/** 从 Vite 编译期注入的 Token */
let token: string = typeof __API_TOKEN__ !== 'undefined' ? __API_TOKEN__ : ''

export function getToken(): string {
  return token
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (token) {
    headers['X-Sonetto-Token'] = token
  }
  const res = await fetch(`${BASE}${url}`, {
    headers,
    ...options,
  })
  if (!res.ok) {
    let detail = `API ${url} 返回 ${res.status}`
    try {
      const body = await res.json()
      if (body.detail) detail += `: ${body.detail}`
    } catch { /* ignore parse errors */ }
    throw new Error(detail)
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

  getMoment: () =>
    request<MomentResponse>('/moment'),

  getMemories: () =>
    request<VignetteResponse>('/memories'),

  getContextUsage: (sessionId: string) =>
    request<ContextUsage & { session_id: string }>(`/sessions/${sessionId}/context-usage`),

  undoMessages: (sessionId: string, n: number = 1) =>
    request<{ deleted_count: number }>(`/sessions/${sessionId}/undo?n=${n}`, { method: 'POST' }),

  getDeepSeekBalance: () =>
    request<DeepSeekBalanceResponse>('/deepseek-balance'),

  health: () =>
    request<HealthResponse>('/health'),

  // ── Provider ──

  listProviders: () =>
    request<ListProvidersResponse>('/providers'),

  getProvider: (id: string) =>
    request<ProviderConfig>(`/providers/${id}`),

  createProvider: (body: Partial<ProviderConfig>) =>
    request<ProviderConfig>('/providers', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateProvider: (id: string, body: Partial<ProviderConfig>) =>
    request<ProviderConfig>(`/providers/${id}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  deleteProvider: (id: string) =>
    request<{ status: string }>(`/providers/${id}`, { method: 'DELETE' }),

  testConnection: (body: { api_key: string; base_url: string; provider_type?: string }) =>
    request<TestConnectionResponse>('/providers/test', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  discoverModels: (body: { api_key: string; base_url: string; provider_type?: string }) =>
    request<DiscoverModelsResponse>('/providers/discover-models', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  discoverModelsForExisting: (id: string) =>
    request<DiscoverModelsResponse>(`/providers/${id}/discover-models`, {
      method: 'POST',
    }),

  testExistingProvider: (id: string) =>
    request<TestConnectionResponse>(`/providers/${id}/test`, {
      method: 'POST',
    }),

  // ── News ──

  listNews: () =>
    request<ListNewsResponse>('/news'),

  // ── Anthropic Skills ──

  listSkills: () =>
    request<ListSkillsResponse>('/skills'),

  listTools: () =>
    request<ListToolsResponse>('/tools'),

  // ── Const 固定会话 ──

  constifySession: (id: string, name: string) =>
    request<ConstifyResponse>(`/sessions/${id}/const`, {
      method: 'POST',
      body: JSON.stringify({ name }),
    }),

  unconstifySession: (id: string) =>
    request<{ status: string }>(`/sessions/${id}/const`, { method: 'DELETE' }),

  generateSessionTitle: (id: string) =>
    request<{ title: string }>(`/sessions/${id}/generate-title`, { method: 'POST' }),

  // ── Persona 人设 ──

  getPersona: (type: 'soul' | 'user') =>
    request<{ content: string; type: string }>(`/persona?type=${type}`),

  updatePersona: (type: 'soul' | 'user', content: string) =>
    request<{ content: string; type: string }>(`/persona?type=${type}`, {
      method: 'PUT',
      body: JSON.stringify({ content }),
    }),

  // ── Path Whitelist 路径白名单 ──

  listWhitelist: () =>
    request<ListWhitelistResponse>('/path-whitelist'),

  addWhitelistEntry: (entry: { path: string; description: string }) =>
    request<WhitelistEntry>('/path-whitelist', {
      method: 'POST',
      body: JSON.stringify(entry),
    }),

  updateWhitelistEntry: (index: number, entry: { path: string; description: string }) =>
    request<WhitelistEntry>(`/path-whitelist/${index}`, {
      method: 'PUT',
      body: JSON.stringify(entry),
    }),

  deleteWhitelistEntry: (index: number) =>
    request<{ status: string }>(`/path-whitelist/${index}`, { method: 'DELETE' }),

  // ── 文件选择器 ──

  selectFile: (type: 'file' | 'folder') =>
    request<{ path: string | null }>(`/select-file?type=${type}`),

  selectFolder: () =>
    request<{ path: string | null }>('/select-file?type=folder'),

  // ── 路径安全检查 ──

  checkPathBlocked: (path: string) =>
    request<{ blocked: boolean; reason: string | null; blocker_path: string | null }>(
      `/check-path-blocked?path=${encodeURIComponent(path)}`
    ),

  // ── SonettoBlocker 拒止锚 ──

  listBlockers: () =>
    request<ListBlockerResponse>('/sonetto-blocker'),

  addBlocker: (entry: { path: string; description: string }) =>
    request<BlockerEntry>('/sonetto-blocker', {
      method: 'POST',
      body: JSON.stringify(entry),
    }),

  deleteBlocker: (index: number) =>
    request<{ status: string }>(`/sonetto-blocker/${index}`, { method: 'DELETE' }),
}
