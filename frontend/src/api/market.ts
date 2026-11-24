import { requestJson } from './client'
import type {
  Distribution,
  MarketOverview,
  RolesData,
  SkillDemand,
  TrendData,
} from '@/types/market'

function query(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value))
  }
  const suffix = search.toString()
  return suffix ? `?${suffix}` : ''
}

export function getMarketOverview(role?: string): Promise<MarketOverview> {
  return requestJson<MarketOverview>(`/api/market/overview${query({ role })}`)
}

export function getMarketSkills(role?: string, limit = 20): Promise<SkillDemand> {
  return requestJson<SkillDemand>(
    `/api/market/skills${query({ role, limit })}`,
  )
}

export function getMarketDistribution(
  dimension: 'education' | 'experience' | 'location',
  role?: string,
): Promise<Distribution> {
  return requestJson<Distribution>(
    `/api/market/distributions${query({ dimension, role })}`,
  )
}

export function getMarketTrends(role?: string): Promise<TrendData> {
  return requestJson<TrendData>(`/api/market/trends${query({ role })}`)
}

export function getMarketRoles(): Promise<RolesData> {
  return requestJson<RolesData>('/api/market/roles')
}