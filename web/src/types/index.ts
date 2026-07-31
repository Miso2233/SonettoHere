import type { FileRef, ParsedRef } from '@/utils/references'

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
  payload: { call_id: string; tool_name: string; input: string }
}

export interface ToolEndEvent {
  type: 'tool_end'
  payload: { call_id: string; tool_name: string; output: string; elapsed: number; tool_data?: Record<string, unknown> }
}

export interface ToolErrorEvent {
  type: 'tool_error'
  payload: { call_id: string; tool_name: string; error: string }
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

/** memory_search_start — 前端语义记忆搜索开始 */
export interface MemorySearchStartEvent {
  type: 'memory_search_start'
  payload: {
    turn_id: string
    interaction_id: string
  }
}

/** memory_search_skipped — 前端语义记忆搜索已被跳过 */
export interface MemorySearchSkippedEvent {
  type: 'memory_search_skipped'
  payload: Record<string, never>
}

/** memory_search_done — 前端语义记忆搜索完成 */
export interface MemorySearchDoneEvent {
  type: 'memory_search_done'
  payload: {
    total: number
    fresh: number
  }
}

/** message_queued — Agent 输出期间发送的消息已挂起到服务端队列 */
export interface MessageQueuedEvent {
  type: 'message_queued'
  payload: {
    pending_id: string
    text: string
    position: number
  }
}

/** pending_consumed — 排队消息已被注入 Agent 上下文 */
export interface PendingConsumedEvent {
  type: 'pending_consumed'
  payload: {
    /** 被消费的排队消息（按消费顺序），含文本供前端渲染 */
    pending: Array<{ pending_id: string; text: string }>
    /** mid_turn：注入当前轮（工具之间渲染为用户气泡）；new_turn：合并为新的一轮 */
    mode: 'mid_turn' | 'new_turn'
    /** new_turn 模式下合并后的用户消息文本 */
    text?: string
  }
}

/** pending_sync — WebSocket 重连时同步服务端挂起队列 */
export interface PendingSyncEvent {
  type: 'pending_sync'
  payload: {
    pending: Array<{ pending_id: string; text: string; position: number }>
  }
}

/** pending_cancelled — 用户点击停止，排队消息被丢弃 */
export interface PendingCancelledEvent {
  type: 'pending_cancelled'
  payload: {
    pending_ids: string[]
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
  | MemorySearchStartEvent
  | MemorySearchSkippedEvent
  | MemorySearchDoneEvent
  | MessageQueuedEvent
  | PendingConsumedEvent
  | PendingSyncEvent
  | PendingCancelledEvent

// === WebSocket 客户端 → 服务端消息 ===

export interface ChatMessage {
  type: 'chat'
  payload: {
    message: string
    private?: boolean
    skip_recall?: boolean
    auto_approve?: boolean
    provider_id?: string
    model_name?: string
    /** 图像认知模式：图片 ref 被移除，后端 base64 编码后注入上下文 */
    image_recognition?: boolean
    /** 图像认知模式下的图片文件绝对路径列表 */
    image_refs?: string[]
    /** 客户端生成的消息 ID，后端用作 pending_id 以关联入队确认 */
    client_msg_id?: string
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

/** 会话中途更新 auto_approve 设置 */
export interface UpdateAutoApproveMessage {
  type: 'update_auto_approve'
  payload: {
    auto_approve: boolean
  }
}

/** skip_memory_search — 用户跳过当前轮的语义记忆搜索 */
export interface SkipMemorySearchMessage {
  type: 'skip_memory_search'
  payload: {
    interaction_id: string
  }
}

/** remove_pending — 从排队队列移除一条消息（不取消正在运行的 Agent） */
export interface RemovePendingMessage {
  type: 'remove_pending'
  payload: {
    pending_id: string
  }
}

/** clear_pending — 清空全部排队消息（不取消正在运行的 Agent） */
export interface ClearPendingMessage {
  type: 'clear_pending'
  payload: Record<string, never>
}

export type ClientMessage = ChatMessage | CancelMessage | PingMessage | UserResponseMessage | UpdateAutoApproveMessage | SkipMemorySearchMessage | RemovePendingMessage | ClearPendingMessage

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
  callId?: string
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

/** 工具间隙注入的用户消息（渲染为工具之间的用户气泡） */
export interface UserMessageEvent {
  kind: 'user_message'
  content: string
  /** 消息内引用的解析结果（引用 chip） */
  refs?: ParsedRef[]
}

export type TurnEvent = ThinkingBlock | ToolCall | MemoryToolEvent | UserMessageEvent

export interface ChatTurn {
  id: string
  userMessage: string
  refs: ParsedRef[]
  /** 图像认知模式下发送的图片引用（用于 UI 展示） */
  imageRefs?: FileRef[]
  events: TurnEvent[]
  memoryEvents?: MemoryToolEvent[]
  finalAnswer: string | null
  /** 后端生成的 turn_id，用于关联后台记忆 consumer 的事件 */
  turnId?: string
  /** 当前轮的语义记忆搜索结果 */
  memorySearch?: { status: 'searching'; skipInteractionId?: string } | { status: 'skipped' } | { status: 'done'; total: number; fresh: number }
}

/** 前端展示的排队消息气泡 */
export interface PendingMessage {
  /** pending_id（message_queued ack 后替换为服务端 ID） */
  id: string
  text: string
  /** queued：等待注入；injected：已注入当前轮 */
  status: 'queued' | 'injected'
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
  long_term: string
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
  hit: number
  _sort_time: string
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

export interface BreakdownPart {
  key?: string
  label: string
  tokens: number
  count?: number  // 仅 messages 使用
}

export interface BreakdownGroup {
  total: number
  usage_percent: number
  parts: BreakdownPart[]
}

export interface TokenBreakdown {
  system_prompt: BreakdownGroup
  messages: BreakdownGroup
}

export interface ContextUsage {
  current_tokens: number
  max_tokens: number
  usage_percent: number
  model_name: string
  breakdown?: TokenBreakdown
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
  model_vision?: Record<string, boolean>
  is_default_provider?: boolean
  default_model?: string | null
  model_context_windows?: Record<string, number>
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
  default_model_warning?: string
  model_context_windows?: Record<string, number>
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

// === 工具环境变量 ===

export interface EnvVarItem {
  key: string
  label: string
  description: string
  value: string
  is_set: boolean
}

export interface ListEnvVarsResponse {
  env_vars: EnvVarItem[]
}

export interface UpdateEnvVarResponse {
  status: string
  key: string
  masked_value: string
}
