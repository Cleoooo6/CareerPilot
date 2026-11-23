export interface MarketSource {
  name: string
  source_type: string
  dataset_kind: string
  license_note: string
  base_url: string | null
}

export interface MarketMeta {
  sample_size: number
  sample_sufficient: boolean
  period_start: string | null
  period_end: string | null
  updated_at: string | null
  dataset_kinds: string[]
  sources: MarketSource[]
  warnings: string[]
}

export interface MarketCountItem {
  name: string
  count: number
  share: number
}

export interface SkillDemandItem {
  skill: string
  count: number
  share: number
  rank: number
}

export interface MarketRoleSkill {
  role: string
  skills: SkillDemandItem[]
}

export interface MarketOverview {
  total_jobs: number
  total_companies: number
  total_roles: number
  total_locations: number
  top_roles: MarketCountItem[]
  top_skills: SkillDemandItem[]
  role_skills: MarketRoleSkill[]
  meta: MarketMeta
}

export interface SkillDemand {
  items: SkillDemandItem[]
  meta: MarketMeta
}

export interface Distribution {
  dimension: string
  items: MarketCountItem[]
  meta: MarketMeta
}

export interface TrendPoint {
  period: string
  count: number
}

export interface TrendData {
  points: TrendPoint[]
  insufficient_data: boolean
  meta: MarketMeta
}

export interface RolesData {
  items: string[]
  meta: MarketMeta
}