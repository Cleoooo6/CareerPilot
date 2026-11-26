import { requestJson } from './client'
import type {
  Distribution,
  MarketOverview,
  RolesData,
  SkillDemand,
  TrendData,
} from '@/types/market'
import type {
  IndustryTrendsData,
  PersonalIndustryTrendsData,
} from '@/types/industryTrends'
import type { PulseIndustryFilter } from '@/types/industryPulse'

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value))
  }
  const suffix = search.toString()
  return suffix ? `?${suffix}` : ''
}

export function getMarketOverview(
  role?: string,
  industry: PulseIndustryFilter = 'all',
  months = 12,
): Promise<MarketOverview> {
  return requestJson<MarketOverview>(
    `/api/market/overview${query({ role, industry, months })}`,
  )
}

export function getMarketSkills(
  role?: string,
  limit = 20,
  industry: PulseIndustryFilter = 'all',
  months = 12,
): Promise<SkillDemand> {
  return requestJson<SkillDemand>(
    `/api/market/skills${query({ role, limit, industry, months })}`,
  )
}

export function getMarketDistribution(
  dimension: 'education' | 'experience' | 'location',
  role?: string,
  industry: PulseIndustryFilter = 'all',
  months = 12,
): Promise<Distribution> {
  return requestJson<Distribution>(
    `/api/market/distributions${query({ dimension, role, industry, months })}`,
  )
}

export function getMarketTrends(
  role?: string,
  industry: PulseIndustryFilter = 'all',
  months = 12,
): Promise<TrendData> {
  return requestJson<TrendData>(
    `/api/market/trends${query({ role, industry, months })}`,
  )
}

export function getMarketRoles(
  industry: PulseIndustryFilter = 'all',
  months = 12,
): Promise<RolesData> {
  return requestJson<RolesData>(
    `/api/market/roles${query({ industry, months })}`,
  )
}
export function getIndustryTrends(
  industry: PulseIndustryFilter = 'all',
  months = 12,
): Promise<IndustryTrendsData> {
  return requestJson<IndustryTrendsData>(
    `/api/market/industry-trends${query({ industry, months })}`,
  )
}

export function getPersonalIndustryTrends(
  industry: PulseIndustryFilter = 'all',
  months = 12,
): Promise<PersonalIndustryTrendsData> {
  return requestJson<PersonalIndustryTrendsData>(
    `/api/market/industry-trends/personal${query({ industry, months })}`,
  )
}
