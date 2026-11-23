import { describe, expect, it } from 'vitest'

import { parseSseBuffer } from '@/sse/parser'

describe('parseSseBuffer', () => {
  it('parses one complete frame', () => {
    const text = 'event: task_started\nid: 1\ndata: {"event":"task_started"}\n\n'
    const { frames, rest } = parseSseBuffer(text)
    expect(rest).toBe('')
    expect(frames).toHaveLength(1)
    expect(frames[0].event).toBe('task_started')
    expect(frames[0].id).toBe('1')
    expect(frames[0].data).toBe('{"event":"task_started"}')
  })

  it('keeps an incomplete frame in rest and completes it later', () => {
    const first = parseSseBuffer('event: node_started\nid: 2\ndata: {"node":')
    expect(first.frames).toHaveLength(0)
    expect(first.rest).toContain('node_started')

    const second = parseSseBuffer(`${first.rest}"INTENT"}\n\n`)
    expect(second.frames).toHaveLength(1)
    expect(second.frames[0].event).toBe('node_started')
    expect(second.frames[0].data).toBe('{"node":"INTENT"}')
  })

  it('normalizes CRLF and parses multiple frames', () => {
    const text =
      'event: a\r\nid: 1\r\ndata: one\r\n\r\nevent: b\r\nid: 2\r\ndata: two\r\n\r\n'
    const { frames, rest } = parseSseBuffer(text)
    expect(rest).toBe('')
    expect(frames.map((frame) => frame.event)).toEqual(['a', 'b'])
    expect(frames.map((frame) => frame.data)).toEqual(['one', 'two'])
  })

  it('joins multiple data lines', () => {
    const text = 'event: a\nid: 1\ndata: line1\ndata: line2\n\n'
    const { frames } = parseSseBuffer(text)
    expect(frames[0].data).toBe('line1\nline2')
  })
})