import type {
  HealthResponse,
  DeepSeekBalanceResponse,
  ListNewsResponse,
} from '@/types'
import { request, requestFireAndForget } from './client'

export const systemApi = {
  health: () =>
    request<HealthResponse>('/health'),

  restart: () =>
    requestFireAndForget('/restart', { method: 'POST' }),

  listNews: () =>
    request<ListNewsResponse>('/news'),

  getDeepSeekBalance: () =>
    request<DeepSeekBalanceResponse>('/deepseek-balance'),
}
