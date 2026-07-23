import { request, requestBlob } from './client'

export const filesApi = {
  /** 打开系统文件/文件夹选择器 */
  selectFile: (type: 'file' | 'folder') =>
    request<{ path: string | null }>(`/select-file?type=${type}`),

  /** 打开系统文件夹选择器（selectFile 的快捷方式） */
  selectFolder: () =>
    request<{ path: string | null }>('/select-file?type=folder'),

  /**
   * 将本地图片路径转为 blob URL，供 <img> 展示
   * 注意：调用方需在适当时机执行 URL.revokeObjectURL() 释放内存
   */
  getImageBlobUrl: async (path: string): Promise<string> => {
    const blob = await requestBlob(`/images/serve?path=${encodeURIComponent(path)}`)
    return URL.createObjectURL(blob)
  },
}
