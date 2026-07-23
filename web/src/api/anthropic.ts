import type {
  ListSkillsResponse,
  ListToolsResponse,
  ListMacrosResponse,
} from '@/types'
import { request } from './client'

export const anthropicApi = {
  listSkills: () =>
    request<ListSkillsResponse>('/skills'),

  listTools: () =>
    request<ListToolsResponse>('/tools'),

  listMacros: () =>
    request<ListMacrosResponse>('/macros'),
}
