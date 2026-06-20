import type { ParsedRef } from '@/utils/references'

// === WebSocket 服务端 → 客户端事件 ===

export interface ThinkingStartEvent {
  type: 'thinking_start'
  payload: { timestamp: number }
}

export interface TokenEvent {
  type: 'token'
  payload: { token: string }
}

export interface ThinkingEndEvent {
  type: 'thinking_end'
  payload: { timestamp: number }
}

export interface ToolStartEvent {
  type: 'tool_start'
  payload: { tool_name: string; input: string }
}

export interface ToolEndEvent {
  type: 'tool_end'
  payload: { tool_name: string; output: string; elapsed: number; tool_data?: Record<string, unknown> }
}

export interface ToolErrorEvent {
  type: 'tool_error'
  payload: { tool_name: string; error: string }
}

export interface AnswerEvent {
  type: 'answer'
  payload: { content: string }
}

export interface DoneEvent {
  type: 'done'
  payload: { turn_id?: string; context_usage?: ContextUsage }
}

export interface ErrorEvent {
  type: 'error'
  payload: { code: string; message: string }
}

export interface PongEvent {
  type: 'pong'
  payload: Record<string, never>
}

export interface ContextUsageEvent {
  type: 'context_usage'
  payload: ContextUsage
}

/** ask_user 交互工具向用户展示的问题和选项 */
export interface AskUserEvent {
  type: 'ask_user'
  payload: {
    tool_name: string
    question: string
    mode: 'qa' | 'single_choice' | 'multi_choice' | 'confirm'
    options: string[]
    interaction_id: string
    code?: string
  }
}

/** sub_session_created — 主 Agent 调用 call_sub_agent 后推送 */
export interface SubSessionCreatedEvent {
  type: 'sub_session_created'
  payload: {
    sub_session_id: string
    parent_session_id: string | null
    task: string
    name: string
  }
}

/** memory_tool_start — 后台记忆 consumer 开始调用 CRUD 工具 */
export interface MemoryToolStartEvent {
  type: 'memory_tool_start'
  payload: {
    turn_id: string
    tool_name: string
    input: string
  }
}

/** memory_tool_end — 后台记忆 consumer 的 CRUD 工具执行完毕 */
export interface MemoryToolEndEvent {
  type: 'memory_tool_end'
  payload: {
    turn_id: string
    tool_name: string
    output: string
    elapsed: number
  }
}

/** memory_tool_error — 后台记忆 consumer 的 CRUD 工具执行出错 */
export interface MemoryToolErrorEvent {
  type: 'memory_tool_error'
  payload: {
    turn_id: string
    tool_name: string
    error: string
  }
}

/** memory_start — 后台记忆 consumer 开始处理本轮对话 */
export interface MemoryStartEvent {
  type: 'memory_start'
  payload: {
    turn_id: string
  }
}

/** memory_done — 后台记忆 consumer 处理完毕（无论是否有修改） */
export interface MemoryDoneEvent {
  type: 'memory_done'
  payload: {
    turn_id: string
  }
}

export type ServerEvent =
  | ThinkingStartEvent
  | TokenEvent
  | ThinkingEndEvent
  | ToolStartEvent
  | ToolEndEvent
  | ToolErrorEvent
  | AnswerEvent
  | DoneEvent
  | ErrorEvent
  | PongEvent
  | ContextUsageEvent
  | AskUserEvent
  | SubSessionCreatedEvent
  | MemoryStartEvent
  | MemoryToolStartEvent
  | MemoryToolEndEvent
  | MemoryToolErrorEvent
  | MemoryDoneEvent

// === WebSocket 客户端 → 服务端消息 ===

export interface ChatMessage {
  type: 'chat'
  payload: {
    message: string
    private?: boolean
    auto_approve?: boolean
    provider_id?: string
    model_name?: string
  }
}

export interface CancelMessage {
  type: 'cancel'
  payload: Record<string, never>
}

export interface PingMessage {
  type: 'ping'
  payload: Record<string, never>
}

/** 用户对 ask_user 交互工具的响应 */
export interface UserResponseMessage {
  type: 'user_response'
  payload: {
    interaction_id: string
    response: string | string[]
  }
}

export type ClientMessage = ChatMessage | CancelMessage | PingMessage | UserResponseMessage

// === 前端 UI 状态类型 ===

export interface ThinkingBlock {
  kind: 'thinking'
  tokens: string
  done: boolean
  becameAnswer: boolean
}

/** ask_user 交互工具在前端存储的交互数据 */
export interface AskUserInteraction {
  question: string
  mode: 'qa' | 'single_choice' | 'multi_choice' | 'confirm'
  options: string[]
  interactionId: string
  submitted: boolean
  code?: string
}

export interface ToolCall {
  kind: 'tool'
  name: string
  input: string
  output: string | null
  elapsed: number | null
  status: 'running' | 'done' | 'error'
  toolData?: Record<string, unknown>
  /** ask_user 交互工具的额外数据 */
  interaction?: AskUserInteraction
}

/** 后台记忆 consumer 的 CRUD 工具调用（渲染在轮次底部小字区） */
export interface MemoryToolEvent {
  kind: 'memory_tool'
  name: string
  input: string
  output: string | null
  elapsed: number | null
  status: 'running' | 'done' | 'error'
}

export type TurnEvent = ThinkingBlock | ToolCall | MemoryToolEvent

export interface ChatTurn {
  id: string
  userMessage: string
  refs: ParsedRef[]
  events: TurnEvent[]
  memoryEvents?: MemoryToolEvent[]
  finalAnswer: string | null
  /** 后端生成的 turn_id，用于关联后台记忆 consumer 的事件 */
  turnId?: string
}

// === 会话与 API 类型 ===

export interface SessionInfo {
  session_id: string
  message_count: number
  created_at: number
  last_active?: number
  has_active_agent?: boolean
  is_subagent?: boolean
  auto_approve?: boolean
  is_const?: boolean
  const_name?: string
}

export interface CreateSessionResponse {
  session_id: string
  created_at: number
}

export interface ConstifyResponse {
  session_id: string
  is_const: boolean
  const_name: string
}

export interface ListSessionsResponse {
  sessions: SessionInfo[]
}

export interface NarrativeResponse {
  narrative: string
}

export interface MomentItem {
  id: string
  description: string
  theme: string
  history: Array<{ description: string; time: string }>
}

export interface MomentResponse {
  moment: MomentItem | null
}

// === Vignette：记忆分区瀑布流 ===

export interface MemoryHistoryEntry {
  description: string
  time: string
}

export interface VignetteMemoryItem {
  id: string
  description: string
  history: MemoryHistoryEntry[]
}

export interface VignetteSection {
  theme: string
  items: VignetteMemoryItem[]
}

export interface VignetteResponse {
  sections: VignetteSection[]
}

// === DeepSeek 余额 ===

export interface BalanceInfo {
  currency: string
  total_balance: string
  topped_up_balance: string
  granted_balance: string
}

export interface DeepSeekBalanceResponse {
  is_available: boolean
  balance_infos: BalanceInfo[]
}

// === 上下文窗口用量 ===

export interface ContextUsage {
  current_tokens: number
  max_tokens: number
  usage_percent: number
  model_name: string
}

// === 健康检查 ===

export interface ComponentHealth {
  status: 'ok' | 'error'
  latency_ms: number | null
  detail: string | null
}

export interface HealthResponse {
  status: 'ok' | 'degraded'
  version: string
  llm: ComponentHealth
  memory: ComponentHealth
  native_tools: ComponentHealth
  mcp_tools: ComponentHealth
  anthropic_skills_count: number
  timestamp: number
}

// === 提供商管理 ===

export interface ProviderConfig {
  id: string
  provider_type: string
  label: string
  api_key: string
  base_url: string
  models: string[]
  enabled: boolean
  context_window?: number
}

export interface ListProvidersResponse {
  providers: ProviderConfig[]
}

export interface TestConnectionResponse {
  status: 'ok' | 'error'
  latency_ms: number | null
  detail: string | null
}

export interface DiscoverModelsResponse {
  models: string[]
}

// === 系统更新动态 ===

export interface NewsEntry {
  id: string
  en_title: string | null
  title: string
  description: string
  type: string
  date: string
  tags: string[]
  version: string
  pr_number: number
}

export interface ListNewsResponse {
  news: NewsEntry[]
}

// === Anthropic Skills ===

export interface SkillInfo {
  name: string
  description: string
  path: string
}

export interface ListSkillsResponse {
  skills: SkillInfo[]
}

export interface ListMacrosResponse {
  macros: SkillInfo[]
}

// === 内置工具 ===

export interface ToolInfo {
  name: string
  description: string
}

export interface ListToolsResponse {
  tools: ToolInfo[]
}

// === 路径白名单 ===

export interface WhitelistEntry {
  path: string
  description: string
  recursive: boolean
}

export interface ListWhitelistResponse {
  entries: WhitelistEntry[]
}

// === SonettoBlocker 拒止锚 ===

export interface BlockerEntry {
  path: string
  description: string
}

export interface ListBlockerResponse {
  entries: BlockerEntry[]
}
