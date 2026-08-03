import type { ListStudiosResponse, StudioDocument, StudioInfo, StudioSchemaResponse } from '@/types'
import { request } from './client'

export const studiosApi = {
  /** 获取所有工作坊（studios/*.yaml） */
  listStudios: () =>
    request<ListStudiosResponse>('/studios'),

  /** 获取 STUDIO_SPEC schema（供表单动态生成控件） */
  getStudioSchema: () =>
    request<StudioSchemaResponse>('/studios/schema'),

  /** 按 name 获取工作坊完整文档（编辑回填） */
  getStudio: (name: string) =>
    request<StudioDocument>(`/studios/${encodeURIComponent(name)}`),

  /** 新建工作坊 */
  createStudio: (document: StudioDocument) =>
    request<StudioInfo>('/studios', {
      method: 'POST',
      body: JSON.stringify({ document }),
    }),

  /** 更新工作坊（改名会重命名文件） */
  updateStudio: (name: string, document: StudioDocument) =>
    request<StudioInfo>(`/studios/${encodeURIComponent(name)}`, {
      method: 'PUT',
      body: JSON.stringify({ document }),
    }),

  /** 删除工作坊 */
  deleteStudio: (name: string) =>
    request<{ status: string }>(`/studios/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    }),
}
