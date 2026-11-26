import { describe, expect, it } from 'vitest'

import { PULSE_TIME_ZONE, formatPulseDate } from '@/utils/pulseTime'

describe('formatPulseDate', () => {
  it('renders UTC RSS timestamps in Asia/Shanghai', () => {
    expect(PULSE_TIME_ZONE).toBe('Asia/Shanghai')
    const text = formatPulseDate(
      '2026-11-25T03:32:05Z',
      new Date('2026-11-25T06:00:00Z').getTime(),
    )
    expect(text).toContain('2026/11/25')
    expect(text).toContain('11:32')
  })

  it('never displays a future timestamp as a normal time', () => {
    expect(
      formatPulseDate(
        '2026-11-25T14:00:00Z',
        new Date('2026-11-25T06:00:00Z').getTime(),
      ),
    ).toBe('发布时间待核实（晚于当前时间）')
  })

  it('handles missing and invalid timestamps', () => {
    expect(formatPulseDate(null)).toBe('发布时间缺失')
    expect(formatPulseDate('not-a-date')).toBe('发布时间待核实')
  })
})