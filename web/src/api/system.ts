import type {
  HealthResponse,
  DeepSeekBalanceResponse,
  ListNewsResponse,
} from '@/types'
import { request, requestFireAndForget } from './client'

export const systemApi = {
  /** 健康检查 */
  health: () =>
    request<HealthResponse>('/health'),

  /**
   * 重启后端服务
   * 服务器关闭连接会导致 fetch 抛错，由 client.requestFireAndForget 静默处理
   */
  restart: () =>
    requestFireAndForget('/restart', { method: 'POST' }),

  /** 获取系统更新动态列表 */
  listNews: () =>
    request<ListNewsResponse>('/news'),

  /** 查询 DeepSeek API 余额 */
  getDeepSeekBalance: () =>
    request<DeepSeekBalanceResponse>('/deepseek-balance'),
}
