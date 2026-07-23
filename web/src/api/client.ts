declare const __API_TOKEN__: string

const BASE = '/api'

let token: string = typeof __API_TOKEN__ !== 'undefined' ? __API_TOKEN__ : ''

/** 获取当前 API Token */
export function getToken(): string {
  return token
}

export function setToken(t: string) {
  token = t
}

export type ConnectionTestInput = {
  api_key: string
  base_url: string
  provider_type?: string
}

/**
 * 通用 API 请求
 * @param url - 请求路径（自动拼接 BASE）
 * @param options - 额外的 fetch 配置
 * @returns 解析后的 JSON 响应
 */
export async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (token) {
    headers['X-Sonetto-Token'] = token
  }
  const res = await fetch(`${BASE}${url}`, {
    headers,
    ...options,
  })
  if (!res.ok) {
    let detail = `API ${url} 返回 ${res.status}`
    try {
      const body = await res.json()
      if (body.detail) detail += `: ${body.detail}`
    } catch { /* ignore parse errors */ }
    throw new Error(detail)
  }
  return res.json()
}

/** 发起请求并返回 Blob（用于图片等二进制资源） */
export async function requestBlob(url: string, options?: RequestInit): Promise<Blob> {
  const headers: Record<string, string> = {}
  if (token) headers['X-Sonetto-Token'] = token
  const res = await fetch(`${BASE}${url}`, { headers, ...options })
  if (!res.ok) {
    let detail = `API ${url} 返回 ${res.status}`
    try {
      const body = await res.json()
      if (body.detail) detail += `: ${body.detail}`
    } catch { /* ignore parse errors */ }
    throw new Error(detail)
  }
  return res.blob()
}

/**
 * 发起请求但忽略响应（用于服务器断开连接的场景，如重启）
 * 服务器关闭连接导致 fetch 抛错属于预期行为，由本函数静默吞掉
 */
export async function requestFireAndForget(url: string, options?: RequestInit): Promise<void> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['X-Sonetto-Token'] = token
  try {
    await fetch(`${BASE}${url}`, { headers, ...options })
  } catch { /* expected when server closes connection */ }
}
