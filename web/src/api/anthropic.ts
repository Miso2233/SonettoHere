import type {
  ListSkillsResponse,
  ListToolsResponse,
  ListMacrosResponse,
} from '@/types'
import { request } from './client'

export const anthropicApi = {
  /** 获取所有 Anthropic Skills */
  listSkills: () =>
    request<ListSkillsResponse>('/skills'),

  /** 获取所有内置工具列表 */
  listTools: () =>
    request<ListToolsResponse>('/tools'),

  /** 获取所有宏列表 */
  listMacros: () =>
    request<ListMacrosResponse>('/macros'),
}
