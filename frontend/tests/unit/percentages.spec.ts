import { describe, expect, it } from 'vitest'

import { allocatePercentages } from '@/utils/percentages'

describe('allocatePercentages', () => {
  it('allocates integers summing to 100 for the reported 102% case', () => {
    const result = allocatePercentages([
      { name: '上海', count: 5 },
      { name: '北京', count: 5 },
      { name: '杭州', count: 4 },
      { name: '深圳', count: 4 },
      { name: '广州', count: 3 },
      { name: '成都', count: 3 },
    ])
    expect(Object.values(result).reduce((sum, value) => sum + value, 0)).toBe(100)
    expect(result).toEqual({
      上海: 21,
      北京: 21,
      杭州: 17,
      深圳: 17,
      广州: 12,
      成都: 12,
    })
  })

  it('uses largest remainder and stable order for ties', () => {
    const result = allocatePercentages([
      { name: 'A', count: 1 },
      { name: 'B', count: 1 },
      { name: 'C', count: 1 },
    ])
    expect(result).toEqual({ A: 34, B: 33, C: 33 })
  })

  it('returns empty for no samples', () => {
    expect(allocatePercentages([])).toEqual({})
  })
})