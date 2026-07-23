import { request } from './client'

export const personasApi = {
  /** 获取人设内容（soul = AI 人设，user = 用户人设） */
  getPersona: (type: 'soul' | 'user') =>
    request<{ content: string; type: string }>(`/persona?type=${type}`),

  /**
   * 更新人设内容
   * @param type - soul（AI）或 user（用户）
   * @param content - 人设文本
   */
  updatePersona: (type: 'soul' | 'user', content: string) =>
    request<{ content: string; type: string }>(`/persona?type=${type}`, {
      method: 'PUT',
      body: JSON.stringify({ content }),
    }),
}
