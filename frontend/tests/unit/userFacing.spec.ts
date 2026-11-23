import { describe, expect, it } from 'vitest'

import { userFacingText } from '@/utils/userFacing'

describe('user facing text', () => {
  it('removes internal mode and implementation terms', () => {
    const text = userFacingText(
      '【Mock 模式】已识别意图：general_chat。当前未调用真实模型，这是用于验证 LangGraph、SSE 与持久化链路的本地回复；不会伪造数据。【Mock LLM】合成数据',
    )
    expect(text).not.toContain('Mock')
    expect(text).not.toContain('general_chat')
    expect(text).not.toContain('LangGraph')
    expect(text).not.toContain('SSE')
    expect(text).not.toContain('持久化链路')
    expect(text).not.toContain('合成')
    expect(text).toContain('演示')
    expect(text).toContain('体验环境')
  })

  it('keeps natural user-facing text unchanged', () => {
    expect(userFacingText('你好，我是 CareerPilot AI')).toBe(
      '你好，我是 CareerPilot AI',
    )
  })
})