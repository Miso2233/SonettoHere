import { request, requestBlob } from './client'

export const filesApi = {
  selectFile: (type: 'file' | 'folder') =>
    request<{ path: string | null }>(`/select-file?type=${type}`),

  selectFolder: () =>
    request<{ path: string | null }>('/select-file?type=folder'),

  /** 将本地图片路径转为 blob URL，供 <img> 展示。返回的 URL 需在适当时机 revoke。 */
  getImageBlobUrl: async (path: string): Promise<string> => {
    const blob = await requestBlob(`/images/serve?path=${encodeURIComponent(path)}`)
    return URL.createObjectURL(blob)
  },
}
