import type {
  ProviderConfig,
  ListProvidersResponse,
  TestConnectionResponse,
  DiscoverModelsResponse,
} from '@/types'
import { request, type ConnectionTestInput } from './client'

export const providersApi = {
  /** 获取所有供应商列表 */
  listProviders: () =>
    request<ListProvidersResponse>('/providers'),

  /** 获取指定供应商详情 */
  getProvider: (id: string) =>
    request<ProviderConfig>(`/providers/${id}`),

  /**
   * 新增供应商
   * @param body - 供应商配置（id 由后端生成，可不传）
   */
  createProvider: (body: Partial<ProviderConfig>) =>
    request<ProviderConfig>('/providers', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /**
   * 更新供应商配置
   * @param id - 供应商 ID
   * @param body - 要更新的字段
   */
  updateProvider: (id: string, body: Partial<ProviderConfig>) =>
    request<ProviderConfig>(`/providers/${id}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  /**
   * 删除供应商
   * @param id - 供应商 ID
   */
  deleteProvider: (id: string) =>
    request<{ status: string }>(`/providers/${id}`, { method: 'DELETE' }),

  /**
   * 测试供应商连接是否可用
   * @param body - 连接信息（API Key、Base URL 等）
   * @returns 连接状态和延迟
   */
  testConnection: (body: ConnectionTestInput) =>
    request<TestConnectionResponse>('/providers/test', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /**
   * 从供应商拉取可用模型列表
   * @param body - 连接信息
   * @returns 模型 ID 列表
   */
  discoverModels: (body: ConnectionTestInput) =>
    request<DiscoverModelsResponse>('/providers/discover-models', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /**
   * 为已有供应商重新拉取可用模型
   * @param id - 供应商 ID
   */
  discoverModelsForExisting: (id: string) =>
    request<DiscoverModelsResponse>(`/providers/${id}/discover-models`, {
      method: 'POST',
    }),

  /**
   * 测试已保存的供应商连接
   * @param id - 供应商 ID
   */
  testExistingProvider: (id: string) =>
    request<TestConnectionResponse>(`/providers/${id}/test`, {
      method: 'POST',
    }),
}
