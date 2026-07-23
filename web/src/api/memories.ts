import type {
  NarrativeResponse,
  MomentResponse,
  VignetteResponse,
} from '@/types'
import { request } from './client'

export const memoriesApi = {
  getNarrative: () =>
    request<NarrativeResponse>('/long-term'),

  getMoment: () =>
    request<MomentResponse>('/moment'),

  getMemories: () =>
    request<VignetteResponse>('/memories'),

  deleteMemory: (id: string) =>
    request<{ status: string; id: string; description: string }>(`/memories/${id}`, { method: 'DELETE' }),
}
