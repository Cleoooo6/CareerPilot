import { describe, expect, it } from 'vitest'

import { initialChatState, reduceEvent } from '@/stores/chat'
import type { SseEvent } from '@/types/chat'

function event(
  name: SseEvent['event'],
  data: Record<string, unknown>,
  eventId = 1,
): SseEvent {
  return {
    task_id: 'task-1',
    event_id: eventId,
    event: name,
    data,
    timestamp: '2026-11-23T12:00:00Z',
  }
}

describe('reduceEvent', () => {
  it('moves from idle to streaming, tracks intent and nodes', () => {
    let state = initialChatState()
    state = reduceEvent(state, event('task_started', {}))
    expect(state.status).toBe('streaming')
    expect(state.intent).toBeNull()

    state = reduceEvent(
      state,
      event('intent_detected', { intent: 'general_chat' }, 2),
    )
    expect(state.intent).toBe('general_chat')

    state = reduceEvent(state, event('node_started', { node: 'INTENT' }, 3))
    expect(state.timeline).toEqual([
      expect.objectContaining({ node: 'INTENT', status: 'running' }),
    ])

    state = reduceEvent(
      state,
      event('node_completed', { node: 'INTENT', status: 'completed' }, 4),
    )
    expect(state.timeline[0].status).toBe('completed')
  })

  it('accumulates content deltas into one assistant message', () => {
    let state = initialChatState()
    state = reduceEvent(state, event('task_started', {}))
    state = reduceEvent(state, event('content_delta', { content: '你好' }, 2))
    state = reduceEvent(state, event('content_delta', { content: '，世界' }, 3))
    expect(state.messages).toHaveLength(1)
    expect(state.messages[0].role).toBe('assistant')
    expect(state.messages[0].content).toBe('你好，世界')
    expect(state.activeAssistantId).toBeTruthy()
  })

  it('replaces the streaming message with the final assistant content', () => {
    let state = initialChatState()
    state = reduceEvent(state, event('content_delta', { content: '片段' }))
    state = reduceEvent(
      state,
      event('assistant_message', { content: '完整回复' }, 2),
    )
    expect(state.messages).toHaveLength(1)
    expect(state.messages[0].content).toBe('完整回复')
    expect(state.activeAssistantId).toBeNull()

    state = reduceEvent(state, event('task_completed', { status: 'completed' }, 3))
    expect(state.status).toBe('completed')
  })

  it('appends a full assistant message when no stream was received', () => {
    let state = initialChatState()
    state = reduceEvent(
      state,
      event('assistant_message', { content: '你好，我是 CareerPilot AI' }),
    )
    expect(state.messages).toHaveLength(1)
    expect(state.messages[0].role).toBe('assistant')
  })

  it('tracks profile usage from intent events', () => {
    let state = initialChatState()
    state = reduceEvent(
      state,
      event('intent_detected', { intent: 'resume', profile_used: true }),
    )
    expect(state.intent).toBe('resume')
    expect(state.profileUsed).toBe(true)

    state = reduceEvent(state, event('task_started', {}, 2))
    expect(state.profileUsed).toBe(false)
  })

  it('reports task failure without treating it as success', () => {
    let state = initialChatState()
    state = reduceEvent(
      state,
      event('task_failed', { code: 'WORKFLOW_FAILED', message: '执行失败' }),
    )
    expect(state.status).toBe('failed')
    expect(state.error).toEqual({ code: 'WORKFLOW_FAILED', message: '执行失败' })
  })
})