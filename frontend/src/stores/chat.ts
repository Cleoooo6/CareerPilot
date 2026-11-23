import { reactive } from 'vue'

import { ApiError, isAbortError } from '@/api/client'
import {
  createConversation,
  getLLMStatus,
  getTools,
  listMessages,
} from '@/api/chat'
import { streamChat } from '@/sse/client'
import type {
  ChatError,
  ChatMessage,
  ChatState,
  ChatStatus,
  LLMStatusDto,
  SseEvent,
  TimelineItem,
  ToolListDto,
} from '@/types/chat'

const CONVERSATION_KEY = 'careerpilot:conversation_id'

export interface ChatStoreState extends ChatState {
  llmStatus: LLMStatusDto | null
  tools: ToolListDto | null
  controller: AbortController | null
}

export function initialChatState(): ChatState {
  return {
    conversationId: '',
    messages: [],
    timeline: [],
    status: 'idle',
    error: null,
    lastUserMessage: '',
  }
}

function messageId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `msg-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function upsertTimeline(
  timeline: TimelineItem[],
  node: string,
  status: TimelineItem['status'],
): TimelineItem[] {
  const index = timeline.findIndex((item) => item.node === node)
  const next = [...timeline]
  const item: TimelineItem = { node, status, updatedAt: new Date().toISOString() }
  if (index === -1) next.push(item)
  else next[index] = item
  return next
}

export function reduceEvent(state: ChatState, event: SseEvent): ChatState {
  const next: ChatState = {
    ...state,
    messages: [...state.messages],
    timeline: [...state.timeline],
  }
  switch (event.event) {
    case 'task_started':
      next.status = 'streaming'
      next.error = null
      break
    case 'node_started':
      next.timeline = upsertTimeline(
        next.timeline,
        String(event.data.node ?? 'UNKNOWN'),
        'running',
      )
      break
    case 'node_completed': {
      const node = String(event.data.node ?? 'UNKNOWN')
      const status = event.data.status === 'failed' ? 'failed' : 'completed'
      next.timeline = upsertTimeline(next.timeline, node, status)
      break
    }
    case 'assistant_message':
      next.messages.push({
        id: messageId(),
        role: 'assistant',
        content: String(event.data.content ?? ''),
        createdAt: event.timestamp,
      })
      break
    case 'task_completed':
      next.status = 'completed'
      break
    case 'task_failed': {
      next.status = 'failed'
      const code = String(event.data.code ?? 'TASK_FAILED')
      const message = String(event.data.message ?? '执行失败，请稍后重试')
      next.error = { code, message }
      break
    }
  }
  return next
}

function toChatMessage(message: {
  id: string
  role: string
  content: string
  created_at: string
}): ChatMessage {
  return {
    id: message.id,
    role: message.role === 'user' ? 'user' : 'assistant',
    content: message.content,
    createdAt: message.created_at,
  }
}

function errorToChatError(error: unknown): ChatError {
  if (error instanceof ApiError) {
    return { code: error.code, message: error.message }
  }
  return { code: 'UNKNOWN_ERROR', message: '执行失败，请稍后重试' }
}


const state = reactive<ChatStoreState>({
  ...initialChatState(),
  llmStatus: null,
  tools: null,
  controller: null,
})

function isBusy(): boolean {
  return state.status === 'sending' || state.status === 'streaming'
}

function clearError(): void {
  state.error = null
}

async function loadMeta(): Promise<void> {
  const [llm, tools] = await Promise.allSettled([getLLMStatus(), getTools()])
  if (llm.status === 'fulfilled') state.llmStatus = llm.value
  if (tools.status === 'fulfilled') state.tools = tools.value
}

async function restore(): Promise<void> {
  if (typeof localStorage === 'undefined') return
  const stored = localStorage.getItem(CONVERSATION_KEY)
  if (!stored) return
  try {
    const result = await listMessages(stored)
    state.conversationId = stored
    state.messages = result.items.map(toChatMessage)
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      localStorage.removeItem(CONVERSATION_KEY)
    }
  }
}

async function send(content: string): Promise<void> {
  const text = content.trim()
  if (!text || isBusy()) return

  state.lastUserMessage = text
  state.error = null
  state.timeline = []
  state.status = 'sending'
  state.messages.push({
    id: messageId(),
    role: 'user',
    content: text,
    createdAt: new Date().toISOString(),
  })

  const controller = new AbortController()
  try {
    if (!state.conversationId) {
      const conversation = await createConversation()
      state.conversationId = conversation.id
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem(CONVERSATION_KEY, conversation.id)
      }
    }
    state.status = 'streaming'
    state.controller = controller
    await streamChat({
      conversationId: state.conversationId,
      content: text,
      signal: controller.signal,
      onEvent: (event) => {
        const next = reduceEvent(state, event)
        state.messages = next.messages
        state.timeline = next.timeline
        state.status = next.status
        state.error = next.error
      },
    })
    if (state.status === 'streaming') state.status = 'completed'
  } catch (error) {
    if (isAbortError(error)) {
      state.status = 'idle'
      state.timeline = state.timeline.map((item) =>
        item.status === 'running' ? { ...item, status: 'failed' } : item,
      )
      return
    }
    state.status = 'failed'
    state.error = errorToChatError(error)
  } finally {
    state.controller = null
  }
}

function stop(): void {
  state.controller?.abort()
}

export const chatStore = Object.assign(state, {
  isBusy,
  clearError,
  loadMeta,
  restore,
  send,
  stop,
})

export function useChatStore() {
  return chatStore
}