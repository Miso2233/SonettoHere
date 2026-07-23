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

  /** 获取路径白名单列表 */
  listWhitelist: () =>
    request<ListWhitelistResponse>('/path-whitelist'),

  /**
   * 添加路径白名单条目
   * @param entry - 路径和描述
   */
  addWhitelistEntry: (entry: { path: string; description: string }) =>
    request<WhitelistEntry>('/path-whitelist', {
      method: 'POST',
      body: JSON.stringify(entry),
    }),

  /**
   * 更新指定白名单条目
   * @param index - 条目序号
   * @param entry - 新路径和描述
   */
  updateWhitelistEntry: (index: number, entry: { path: string; description: string }) =>
    request<WhitelistEntry>(`/path-whitelist/${index}`, {
      method: 'PUT',
      body: JSON.stringify(entry),
    }),

  /**
   * 删除白名单条目
   * @param index - 条目序号
   */
  deleteWhitelistEntry: (index: number) =>
    request<{ status: string }>(`/path-whitelist/${index}`, { method: 'DELETE' }),

  // ── SonettoBlocker 拒止锚 ──

  /** 获取拒止锚列表 */
  listBlockers: () =>
    request<ListBlockerResponse>('/sonetto-blocker'),

  /**
   * 添加拒止锚
   * @param entry - 路径和描述
   */
  addBlocker: (entry: { path: string; description: string }) =>
    request<BlockerEntry>('/sonetto-blocker', {
      method: 'POST',
      body: JSON.stringify(entry),
    }),

  /**
   * 删除拒止锚
   * @param index - 条目序号
   */
  deleteBlocker: (index: number) =>
    request<{ status: string }>(`/sonetto-blocker/${index}`, { method: 'DELETE' }),

  // ── 工具环境变量 ──

  /** 获取所有工具环境变量 */
  listEnvVars: () =>
    request<ListEnvVarsResponse>('/env-vars'),

  /**
   * 更新单个环境变量
   * @param key - 变量名
   * @param value - 变量值
   */
  updateEnvVar: (key: string, value: string) =>
    request<UpdateEnvVarResponse>('/env-vars', {
      method: 'PUT',
      body: JSON.stringify({ key, value }),
    }),

  /**
   * 批量更新环境变量
   * @param env_vars - 变量键值对列表
   */
  batchUpdateEnvVars: (env_vars: { key: string; value: string }[]) =>
    request<{ status: string; updated: { key: string; masked_value: string }[] }>('/env-vars/batch', {
      method: 'PUT',
      body: JSON.stringify({ env_vars }),
    }),

  // ── 路径安全检查 ──

  /**
   * 检查路径是否被拒止锚拦截
   * @param path - 待检查的绝对路径
   * @returns 是否被拦截及原因
   */
  checkPathBlocked: (path: string) =>
    request<{ blocked: boolean; reason: string | null; blocker_path: string | null }>(
      `/check-path-blocked?path=${encodeURIComponent(path)}`
    ),
}
