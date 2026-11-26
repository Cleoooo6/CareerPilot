export type PulseIndustry =
  | 'digital_tech_comms'
  | 'finance_insurance'
  | 'manufacturing_industry'
  | 'energy_environment'
  | 'auto_smart_mobility'
  | 'transport_logistics'
  | 'health_life_sciences'
  | 'education_research'
  | 'agriculture_food'
  | 'consumer_retail_services'
  | 'real_estate_construction'
  | 'culture_media_content'
  | 'arts_design'
  | 'sports_industry'
  | 'tourism_hospitality_events'
  | 'enterprise_professional_services'
export type PulseIndustryFilter = 'all' | PulseIndustry
export type PulseRegion = 'all' | 'CN' | 'INTL'
export type PulseAnalysisStatus = 'pending' | 'analyzed' | 'failed' | 'disabled'
export type PulseRelevanceStatus =
  | 'industry_relevant'
  | 'macro_signal'
  | 'needs_review'
  | 'irrelevant'

export interface IndustryPulseArticle {
  id: string
  source_id: string | null
  source_name: string
  source_url: string | null
  industry: PulseIndustry | null
  primary_industry: PulseIndustry | null
  industries: PulseIndustry[]
  industry_labels: string[]
  region: 'CN' | 'INTL'
  content_policy: 'feed_excerpt' | 'metadata_only' | 'blocked'
  relevance_status: PulseRelevanceStatus
  classification_basis: Record<string, unknown>
  legacy_industry: string | null
  taxonomy_version: number
  title: string
  url: string
  canonical_url: string
  summary: string
  published_at: string | null
  fetched_at: string
  ai_summary: string
  career_impact: string
  tags: string[]
  analysis_status: PulseAnalysisStatus
  analysis_error: string
  analysis_details: Record<string, unknown>
  analysis_model: string
  analyzed_at: string | null
  created_at: string
  updated_at: string
  match_reasons?: string[]
  match_types?: string[]
}

export interface IndustryPulseSource {
  key: string
  name: string
  industry: PulseIndustry
  primary_industry_label: string
  industries: PulseIndustry[]
  industry_labels: string[]
  region: 'CN' | 'INTL'
  content_policy: 'feed_excerpt' | 'metadata_only' | 'blocked'
  feed_url: string
  homepage_url: string | null
  license_note: string
  enabled: boolean
  blocked_reason: string
  last_status: 'never' | 'ok' | 'failed' | 'blocked'
  last_error: string
  last_fetched_at: string | null
  legacy_industry?: string | null
  taxonomy_version?: number
}

export interface IndustryPulseRun {
  id: string
  status: 'running' | 'succeeded' | 'partial' | 'failed'
  started_at: string
  finished_at: string | null
  sources_total: number
  sources_ok: number
  sources_failed: number
  articles_fetched: number
  articles_inserted: number
  articles_duplicates: number
  articles_skipped_limit?: number | null
  sources_skipped?: number
  stats_legacy?: boolean
  error_message: string
  details: Array<Record<string, unknown>>
}

export interface IndustryCoverage {
  id: PulseIndustry
  label: string
  scope: string
  majors: string[]
  source_count: number
  article_count: number
}

export interface IndustryPulseData {
  items: IndustryPulseArticle[]
  total: number
  limit: number
  offset: number
  industry: PulseIndustryFilter
  region: PulseRegion
  industries: IndustryCoverage[]
  industry_majors_note: string

  sources: IndustryPulseSource[]
  latest_run: IndustryPulseRun | null
  ai_enabled: boolean
  llm_mode: string
  ai_unavailable_reason: string
  view?: 'all' | 'personal'
  profile_sufficient?: boolean
  profile_missing?: string[]
  personalization_reason?: string
  personal_target_role?: string
  personal_target_industry?: string
  personal_target_location?: string
}