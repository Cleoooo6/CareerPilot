import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/api/chat', () => ({
  createConversation: vi.fn(),
  getLLMStatus: vi.fn(),
  getTools: vi.fn(),
  listMessages: vi.fn(),
}))

import { ApiError } from '@/api/client'
import { listMessages } from '@/api/chat'
import { chatStore, resetChatStore } from '@/stores/chat'

const mockedListMessages = vi.mocked(listMessages)
const CONVERSATION_KEY = 'careerpilot:conversation_id'

describe('chat history restore', () => {
  beforeEach(() => {
    resetChatStore()
    localStorage.clear()
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('loads stored history and exposes success state', async () => {
    localStorage.setItem(CONVERSATION_KEY, 'conversation-1')
    mockedListMessages.mockResolvedValue({
      conversation_id: 'conversation-1',
      items: [
        {
          id: 'message-1',
          conversation_id: 'conversation-1',
          role: 'user',
          content: '你好',
          created_at: '2026-11-24T00:00:00Z',
        },
      ],
    })

    await chatStore.restore()

    expect(chatStore.restoreState).toBe('success')
    expect(chatStore.messages).toHaveLength(1)
    expect(chatStore.messages[0].content).toBe('你好')
  })

  it('treats a missing conversation as a successful empty history', async () => {
    localStorage.setItem(CONVERSATION_KEY, 'missing-conversation')
    mockedListMessages.mockRejectedValue(
      new ApiError(404, 'NOT_FOUND', '会话不存在'),
    )

    await chatStore.restore()

    expect(chatStore.restoreState).toBe('success')
    expect(chatStore.messages).toEqual([])
    expect(localStorage.getItem(CONVERSATION_KEY)).toBeNull()
  })

  it('turns history failures into an explicit retryable error', async () => {
    localStorage.setItem(CONVERSATION_KEY, 'broken-conversation')
    mockedListMessages.mockRejectedValue(
      new ApiError(500, 'INTERNAL_ERROR', '历史消息读取失败'),
    )

    await chatStore.restore()

    expect(chatStore.restoreState).toBe('error')
    expect(chatStore.restoreError?.message).toContain('历史消息读取失败')
    expect(chatStore.messages).toEqual([])
  })

  it('stops the skeleton on timeout even if the request never resolves', async () => {
    vi.useFakeTimers()
    localStorage.setItem(CONVERSATION_KEY, 'slow-conversation')
    mockedListMessages.mockReturnValue(new Promise(() => undefined))

    const restore = chatStore.restore()
    await vi.advanceTimersByTimeAsync(8000)
    await restore

    expect(chatStore.restoreState).toBe('error')
    expect(chatStore.restoreError?.code).toBe('HISTORY_TIMEOUT')
    vi.useRealTimers()
  })
})