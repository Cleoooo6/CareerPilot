import { requestJson } from './client'
import type {
  IndustryPulseArticle,
  IndustryPulseData,
  IndustryPulseRun,
  PulseIndustryFilter,
} from '@/types/industryPulse'

export function getIndustryPulse(params: {
  industry?: PulseIndustryFilter
  region?: 'all' | 'CN' | 'INTL'
  limit?: number
  offset?: number
} = {}): Promise<IndustryPulseData> {
  const query = new URLSearchParams()
  if (params.industry && params.industry !== 'all') query.set('industry', params.industry)
  if (params.region && params.region !== 'all') query.set('region', params.region)
  query.set('limit', String(params.limit ?? 20))
  query.set('offset', String(params.offset ?? 0))
  return requestJson<IndustryPulseData>(`/api/industry-pulse?${query.toString()}`)
}

export function refreshIndustryPulse(): Promise<{ run: IndustryPulseRun }> {
  return requestJson<{ run: IndustryPulseRun }>('/api/industry-pulse/refresh', {
    method: 'POST',
  })
}

export function analyzeIndustryPulseArticle(
  articleId: string,
): Promise<IndustryPulseArticle> {
  return requestJson<IndustryPulseArticle>(
    `/api/industry-pulse/articles/${encodeURIComponent(articleId)}/analyze`,
    { method: 'POST' },
  )
}
export function getPersonalIndustryPulse(params: {
  industry?: PulseIndustryFilter
  region?: 'all' | 'CN' | 'INTL'
  limit?: number
  offset?: number
} = {}): Promise<IndustryPulseData> {
  const query = new URLSearchParams()
  if (params.industry && params.industry !== 'all') query.set('industry', params.industry)
  if (params.region && params.region !== 'all') query.set('region', params.region)
  query.set('limit', String(params.limit ?? 20))
  query.set('offset', String(params.offset ?? 0))
  return requestJson<IndustryPulseData>(
    `/api/industry-pulse/personal?${query.toString()}`,
  )
}
