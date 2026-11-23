import type { MarketMeta } from '@/types/market'

export type Priority = 'high' | 'medium' | 'low'
export type TaskStatus = 'pending' | 'in_progress' | 'completed' | 'abandoned'
export type TaskType = 'learning' | 'practice' | 'review'
export type RoadmapStatus = 'draft' | 'active' | 'archived' | 'discarded'
export type GapBasis = 'market' | 'general'

export interface SkillGapItem {
  name: string
  market_count: number
  market_share: number
  priority: Priority
  reason: string
}

export interface SkillGapProfileSkill {
  name: string
  proficiency: string
  evidence: string
  source: string
  verification: string
}

export interface SkillGap {
  target_role: string
  basis: GapBasis
  reference_only: boolean
  matched: SkillGapItem[]
  to_improve: SkillGapItem[]
  not_recorded: SkillGapItem[]
  profile_skills: SkillGapProfileSkill[]
  meta: MarketMeta
  warnings: string[]
  computed_at: string
}

export interface RoadmapTask {
  id: string
  stage_id: string
  position: number
  title: string
  description: string
  task_type: TaskType
  priority: Priority
  estimated_time: string
  acceptance_criteria: string
  status: TaskStatus
  completed_at: string | null
  outcome: string
  created_at: string
  updated_at: string
}

export interface RoadmapStage {
  id: string
  position: number
  title: string
  goal: string
  duration: string
  priority: Priority
  tasks: RoadmapTask[]
}

export interface Roadmap {
  id: string
  user_id: string
  target_role: string
  status: RoadmapStatus
  version: number
  title: string
  summary: string
  gap: SkillGap | null
  generation_mode: 'mock' | 'real'
  provider: string
  model: string
  created_at: string
  updated_at: string
  confirmed_at: string | null
  stages: RoadmapStage[]
  task_total: number
  task_completed: number
}

export interface RoadmapSummary {
  id: string
  target_role: string
  status: RoadmapStatus
  version: number
  title: string
  generation_mode: 'mock' | 'real'
  created_at: string
  updated_at: string
  confirmed_at: string | null
  task_total: number
  task_completed: number
}

export interface RoadmapState {
  roadmap: Roadmap | null
}

export interface RoadmapSummaryList {
  items: RoadmapSummary[]
}

export interface RoadmapTaskUpdateResult {
  task: RoadmapTask
  roadmap_id: string
  roadmap_version: number
}

export const PRIORITY_LABELS: Record<Priority, string> = {
  high: '高',
  medium: '中',
  low: '低',
}

export const TASK_STATUS_LABELS: Record<TaskStatus, string> = {
  pending: '待开始',
  in_progress: '进行中',
  completed: '已完成',
  abandoned: '已放弃',
}

export const TASK_TYPE_LABELS: Record<TaskType, string> = {
  learning: '学习',
  practice: '实践',
  review: '复盘',
}

export const ROADMAP_STATUS_LABELS: Record<RoadmapStatus, string> = {
  draft: '待确认草稿',
  active: '正式路线',
  archived: '历史版本',
  discarded: '已放弃草稿',
}

export const GAP_BASIS_LABELS: Record<GapBasis, string> = {
  market: '市场依据',
  general: '通用建议',
}