import { ApiError } from './client'
import type { PulseIndustry, PulseItem } from '@/data/industryPulse'

export interface IndustryPulseResponse {
  items: PulseItem[]
  meta: {
    example: boolean
    source: string
    fetched_at: string
  }
}

export async function fetchIndustryPulse(
  _industry: PulseIndustry | 'all',
): Promise<IndustryPulseResponse> {
  throw new ApiError(
    501,
    'INDUSTRY_PULSE_NOT_READY',
    '行业动态接口尚未接入',
  )
}