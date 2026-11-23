export type ChatStatus = 'idle' | 'sending' | 'streaming' | 'completed' | 'failed'
export type TimelineStatus = 'running' | 'completed' | 'failed'

export type SseEventName =
  | 'task_started'
  | 'node_started'
  | 'node_completed'
  | 'intent_detected'
  | 'content_delta'
  | 'assistant_message'
  | 'task_completed'
  | 'task_failed'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  createdAt: string
}

export interface TimelineItem {
  node: string
  status: TimelineStatus
  updatedAt: string
}

export interface ChatError {
  code: string
  message: string
}

export interface ChatState {
  conversationId: string
  messages: ChatMessage[]
  timeline: TimelineItem[]
  status: ChatStatus
  error: ChatError | null
  lastUserMessage: string
  intent: string | null
  activeAssistantId: string | null
  profileUsed: boolean
}

export interface SseEvent {
  task_id: string
  event_id: number
  event: SseEventName
  data: Record<string, unknown>
  timestamp: string
}

export interface ApiEnvelope<T> {
  ok: true
  data: T
  request_id: string
}

export interface ApiErrorEnvelope {
  ok: false
  error: {
    code: string
    message: string
    details: Record<string, unknown>
  }
  request_id: string
}

export interface ConversationDto {
  id: string
  user_id: string
  title: string
  created_at: string
  updated_at: string
}

export interface MessageDto {
  id: string
  conversation_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  created_at: string
}

export interface MessageListDto {
  conversation_id: string
  items: MessageDto[]
}

export interface LLMStatusDto {
  provider: string
  mode: string
  model: string
  base_url: string
  api_key_configured: boolean
  real_calls_enabled: boolean
}

export interface ToolDto {
  name: string
  description: string
  input_schema: Record<string, unknown>
}

export interface ToolListDto {
  registered: ToolDto[]
  planned: string[]
}