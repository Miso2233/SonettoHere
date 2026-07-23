import type {
  ListWhitelistResponse,
  WhitelistEntry,
  ListBlockerResponse,
  BlockerEntry,
  ListEnvVarsResponse,
  UpdateEnvVarResponse,
} from '@/types'
import { request } from './client'

export const settingsApi = {
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

  // ── 工具环境变量 ──

  listEnvVars: () =>
    request<ListEnvVarsResponse>('/env-vars'),

  updateEnvVar: (key: string, value: string) =>
    request<UpdateEnvVarResponse>('/env-vars', {
      method: 'PUT',
      body: JSON.stringify({ key, value }),
    }),

  batchUpdateEnvVars: (env_vars: { key: string; value: string }[]) =>
    request<{ status: string; updated: { key: string; masked_value: string }[] }>('/env-vars/batch', {
      method: 'PUT',
      body: JSON.stringify({ env_vars }),
    }),

  // ── 路径安全检查 ──

  checkPathBlocked: (path: string) =>
    request<{ blocked: boolean; reason: string | null; blocker_path: string | null }>(
      `/check-path-blocked?path=${encodeURIComponent(path)}`
    ),
}
