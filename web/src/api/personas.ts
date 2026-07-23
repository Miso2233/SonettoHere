import { request } from './client'

export const personasApi = {
  getPersona: (type: 'soul' | 'user') =>
    request<{ content: string; type: string }>(`/persona?type=${type}`),

  updatePersona: (type: 'soul' | 'user', content: string) =>
    request<{ content: string; type: string }>(`/persona?type=${type}`, {
      method: 'PUT',
      body: JSON.stringify({ content }),
    }),
}
