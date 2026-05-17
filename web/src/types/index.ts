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
  payload: { turn_id: string; context_usage?: ContextUsage }
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
    mode: 'qa' | 'single_choice' | 'multi_choice'
    options: string[]
    interaction_id: string
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

// === WebSocket 客户端 → 服务端消息 ===

export interface ChatMessage {
  type: 'chat'
  payload: { message: string }
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
  mode: 'qa' | 'single_choice' | 'multi_choice'
  options: string[]
  interactionId: string
  submitted: boolean
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

export type TurnEvent = ThinkingBlock | ToolCall

export interface ChatTurn {
  id: string
  userMessage: string
  events: TurnEvent[]
  finalAnswer: string | null
}

// === 会话与 API 类型 ===

export interface SessionInfo {
  session_id: string
  message_count: number
  created_at: number
  last_active?: number
}

export interface CreateSessionResponse {
  session_id: string
  created_at: number
}

export interface ListSessionsResponse {
  sessions: SessionInfo[]
}

export interface NarrativeResponse {
  narrative: string
}

// === 上下文窗口用量 ===

export interface ContextUsage {
  current_tokens: number
  max_tokens: number
  usage_percent: number
  model_name: string
}
