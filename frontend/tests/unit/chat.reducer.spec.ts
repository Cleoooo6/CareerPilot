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
  it('moves from idle to streaming and tracks nodes', () => {
    let state = initialChatState()
    state = reduceEvent(state, event('task_started', {}))
    expect(state.status).toBe('streaming')

    state = reduceEvent(state, event('node_started', { node: 'INTENT' }, 2))
    expect(state.timeline).toEqual([
      expect.objectContaining({ node: 'INTENT', status: 'running' }),
    ])

    state = reduceEvent(
      state,
      event('node_completed', { node: 'INTENT', status: 'completed' }, 3),
    )
    expect(state.timeline[0].status).toBe('completed')
  })

  it('appends assistant content and completes', () => {
    let state = initialChatState()
    state = reduceEvent(
      state,
      event('assistant_message', { content: '你好，我是 CareerPilot AI' }),
    )
    expect(state.messages).toHaveLength(1)
    expect(state.messages[0].role).toBe('assistant')

    state = reduceEvent(state, event('task_completed', { status: 'completed' }, 2))
    expect(state.status).toBe('completed')
    expect(state.error).toBeNull()
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