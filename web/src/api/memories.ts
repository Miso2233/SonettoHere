import type {
  NarrativeResponse,
  MomentResponse,
  VignetteResponse,
} from '@/types'
import { request } from './client'

export const memoriesApi = {
  /** 获取长篇叙事记忆 */
  getNarrative: () =>
    request<NarrativeResponse>('/long-term'),

  /** 获取当前"瞬间"记忆卡片 */
  getMoment: () =>
    request<MomentResponse>('/moment'),

  /** 获取所有记忆分区（按主题分组的瀑布流数据） */
  getMemories: () =>
    request<VignetteResponse>('/memories'),

  /**
   * 删除一条记忆
   * @param id - 记忆 ID
   */
  deleteMemory: (id: string) =>
    request<{ status: string; id: string; description: string }>(`/memories/${id}`, { method: 'DELETE' }),
}
