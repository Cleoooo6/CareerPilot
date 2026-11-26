import { ApiError, csrfHeaders, isAbortError, notifyUnauthorized } from '@/api/client'
import type { SseEvent, SseEventName } from '@/types/chat'

import { parseSseBuffer } from './parser'

const EVENT_NAMES = new Set<SseEventName>([
  'task_started',
  'node_started',
  'node_completed',
  'intent_detected',
  'content_delta',
  'assistant_message',
  'task_completed',
  'task_failed',
])

const TERMINAL_EVENTS = new Set<SseEventName>(['task_completed', 'task_failed'])

export interface StreamChatOptions {
  conversationId: string
  content: string
  signal?: AbortSignal
  onEvent: (event: SseEvent) => void
}

async function readHttpError(response: Response): Promise<ApiError> {
  try {
    const body = await response.json()
    if (body && body.error) {
      return new ApiError(
        response.status,
        String(body.error.code),
        String(body.error.message),
        body.error.details,
      )
    }
  } catch {
    // ignore malformed error body
  }
  return new ApiError(response.status, 'HTTP_ERROR', `请求失败（HTTP ${response.status}）`)
}

function dispatch(frames: ReturnType<typeof parseSseBuffer>['frames'], onEvent: (event: SseEvent) => void): boolean {
  for (const frame of frames) {
    if (!frame.event || !frame.data) continue
    if (!EVENT_NAMES.has(frame.event as SseEventName)) continue
    let payload: SseEvent
    try {
      payload = JSON.parse(frame.data) as SseEvent
    } catch {
      continue
    }
    if (!payload || payload.event !== frame.event) continue
    if (!payload.task_id || !Number.isInteger(payload.event_id)) continue
    onEvent(payload)
    if (TERMINAL_EVENTS.has(payload.event)) return true
  }
  return false
}

export async function streamChat(options: StreamChatOptions): Promise<void> {
  let response: Response
  try {
    response = await fetch(
      `/api/conversations/${encodeURIComponent(options.conversationId)}/messages`,
      {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
          ...csrfHeaders('POST'),
        },
        body: JSON.stringify({ content: options.content }),
        signal: options.signal,
      },
    )
  } catch (error) {
    if (isAbortError(error)) throw error
    throw new ApiError(0, 'NETWORK_ERROR', '无法连接后端服务', error)
  }

  if (!response.ok) {
    notifyUnauthorized(response.status)
    throw await readHttpError(response)
  }
  if (!response.body) {
    throw new ApiError(0, 'NETWORK_ERROR', '后端未返回事件流')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const { frames, rest } = parseSseBuffer(buffer)
      buffer = rest
      if (dispatch(frames, options.onEvent)) {
        await reader.cancel()
        return
      }
    }
    buffer += decoder.decode()
    if (buffer.trim()) {
      const { frames } = parseSseBuffer(`${buffer}\n\n`)
      dispatch(frames, options.onEvent)
    }
  } finally {
    try {
      reader.releaseLock()
    } catch {
      // reader already cancelled
    }
  }
}