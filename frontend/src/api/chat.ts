import { requestJson } from './client'
import type {
  ConversationDto,
  LLMStatusDto,
  MessageListDto,
  ToolListDto,
} from '@/types/chat'

export function createConversation(title = 'AI 职业咨询'): Promise<ConversationDto> {
  return requestJson<ConversationDto>('/api/conversations', {
    method: 'POST',
    body: JSON.stringify({ title }),
  })
}

export function listMessages(conversationId: string): Promise<MessageListDto> {
  return requestJson<MessageListDto>(
    `/api/conversations/${encodeURIComponent(conversationId)}/messages`,
  )
}

export function getLLMStatus(): Promise<LLMStatusDto> {
  return requestJson<LLMStatusDto>('/api/llm/status')
}

export function getTools(): Promise<ToolListDto> {
  return requestJson<ToolListDto>('/api/tools')
}