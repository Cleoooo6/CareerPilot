import type { PulseIndustry, PulseIndustryFilter } from '@/types/industryPulse'

export type TrendDirection = 'rising' | 'stable' | 'cooling' | 'unclear' | 'insufficient'
export type TrendEvidenceLevel = 'strong' | 'medium' | 'insufficient'
export type TrendBasis = 'market_news' | 'market' | 'news' | 'insufficient'
export type PersonalMatch = 'high' | 'medium' | 'low'

export interface IndustryCatalogItem {
  id: PulseIndustry
  label: string
}

export interface TrendMonthCount {
  period: string
  count: number
}

export interface TrendCountItem {
  name: string
  count: number
}

export interface TrendSkillItem {
  skill: string
  count: number
  share: number
}

export interface TrendNewsItem {
  id: string
  title: string
  source: string
  published_at: string | null
  url: string
}

export interface TrendEvidence {
  news_count: number
  news_source_count: number
  news_period_start: string | null
  news_period_end: string | null
  news_span_days: number
  news_examples: TrendNewsItem[]
  job_count: number
  job_month_count: number
  job_period_start: string | null
  job_period_end: string | null
  job_months: TrendMonthCount[]
  roles: TrendCountItem[]
  skills: TrendSkillItem[]
  locations: TrendCountItem[]
  education: TrendCountItem[]
  experience: TrendCountItem[]
  dataset_kinds: string[]
  synthetic: boolean
  sources: string[]
}

export interface IndustryTrendItem {
  industry_id: PulseIndustry
  label: string
  title: string
  summary: string
  direction: TrendDirection
  confidence: 'high' | 'medium' | 'low'
  evidence_level: TrendEvidenceLevel
  basis: TrendBasis
  period_start: string | null
  period_end: string | null
  news_count: number
  news_source_count: number
  job_count: number
  roles: TrendCountItem[]
  skills: TrendSkillItem[]
  locations: TrendCountItem[]
  data_gaps: string[]
  evidence: TrendEvidence
}

export interface InsufficientIndustry {
  industry_id: PulseIndustry
  label: string
  reason: string
  news_count: number
  job_count: number
}

export interface IndustryTrendsData {
  generated_at: string
  months: number
  industry_filter: PulseIndustryFilter
  items: IndustryTrendItem[]
  insufficient_industries: InsufficientIndustry[]
  warnings: string[]
  industry_catalog: IndustryCatalogItem[]
}

export interface RoadmapTrendSuggestion {
  reason: string
  suggested_skills: string[]
  deprioritize_skills: string[]
  requires_confirmation: boolean
  confirm_url: string
}

export interface PersonalSkillGap {
  name: string
  count: number
  share: number
  recorded: boolean
  evidence_note: string
}

export interface PersonalTrendItem {
  trend: IndustryTrendItem
  relevance_confidence: PersonalMatch
  why_relevant: string[]
  matched_goals: string[]
  matched_skills: string[]
  missing_skills: string[]
  skill_gaps: PersonalSkillGap[]
  affected_roles: TrendCountItem[]
  impact: string
  opportunities: string[]
  risks: string[]
  next_actions: string[]
  roadmap_suggestion: RoadmapTrendSuggestion
  facts: string[]
  inferences: string[]
  suggestions: string[]
}

export interface PersonalIndustryTrendsData {
  generated_at: string
  months: number
  profile_sufficient: boolean
  profile_missing: string[]
  target_role: string
  target_industry: string
  target_industry_label: string
  target_location: string
  items: PersonalTrendItem[]
  insufficient_reason: string
  warnings: string[]
  industry_catalog: IndustryCatalogItem[]
}