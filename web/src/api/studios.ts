import type { ListStudiosResponse } from '@/types'
import { request } from './client'

export const studiosApi = {
  /** 获取所有工作坊（studios/*.yaml） */
  listStudios: () =>
    request<ListStudiosResponse>('/studios'),
}
