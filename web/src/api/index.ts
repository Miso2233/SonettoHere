/**
 * API 客户端 — 统一导出
 *
 * 各领域模块按职责拆分到独立文件：
 *   client.ts     — 基础 request 函数、token、共用类型
 *   sessions.ts   — 会话管理
 *   providers.ts  — 供应商管理
 *   memories.ts   — 记忆/叙事
 *   personas.ts   — 人设
 *   settings.ts   — 白名单、拒止锚、环境变量
 *   system.ts     — 健康检查、系统动态、DeepSeek 余额
 *   anthropic.ts  — Skills / Tools / Macros
 *   files.ts      — 文件选择、图片服务
 */

import { sessionsApi } from './sessions'
import { providersApi } from './providers'
import { memoriesApi } from './memories'
import { personasApi } from './personas'
import { settingsApi } from './settings'
import { systemApi } from './system'
import { anthropicApi } from './anthropic'
import { filesApi } from './files'
import { getToken, setToken } from './client'

export { getToken, setToken }

/** 扁平 API 对象，保持与消费者（组件/stores）的兼容 */
export const api = {
  ...sessionsApi,
  ...providersApi,
  ...memoriesApi,
  ...personasApi,
  ...settingsApi,
  ...systemApi,
  ...anthropicApi,
  ...filesApi,
}

