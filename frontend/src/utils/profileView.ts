import {
  SKILL_SOURCE_LABELS,
  SKILL_VERIFICATION_LABELS,
  type ProfileAnalysisOut,
  type ProfileData,
  type SkillItem,
} from '@/types/profile'
import type { SkillGap } from '@/types/roadmap'

export const UNCATEGORIZED_SKILL = '未分类'

export interface SkillGroup {
  category: string
  skills: SkillItem[]
}

export interface MarketSkillGap {
  matched: string[]
  notRecorded: string[]
}

export function groupSkills(skills: SkillItem[]): SkillGroup[] {
  const groups = new Map<string, SkillItem[]>()
  for (const skill of skills) {
    const category = skill.category.trim() || UNCATEGORIZED_SKILL
    const items = groups.get(category) ?? []
    items.push(skill)
    groups.set(category, items)
  }
  return [...groups.entries()].map(([category, items]) => ({
    category,
    skills: items,
  }))
}

export function proficiencyLabel(value: string): string {
  return value.trim() || '待评估'
}

export function evidenceLabel(skill: SkillItem): string {
  return skill.evidence.trim() || '待补充证据'
}

export function sourceLabel(value: string): string {
  const text = value.trim()
  if (!text) return '来源未记录'
  return SKILL_SOURCE_LABELS[text] ?? text
}

export function verificationLabel(value: string): string {
  const text = value.trim()
  if (!text) return '待确认'
  return SKILL_VERIFICATION_LABELS[text] ?? text
}

export function latestAnalysis(
  analyses: ProfileAnalysisOut[],
): ProfileAnalysisOut | null {
  if (!analyses.length) return null
  return [...analyses].sort((left, right) =>
    right.created_at.localeCompare(left.created_at),
  )[0]
}

export function marketSkillGap(
  skills: SkillItem[],
  demand: { skill: string }[],
): MarketSkillGap {
  const owned = new Set(
    skills.map((skill) => skill.name.trim().toLowerCase()).filter(Boolean),
  )
  const matched: string[] = []
  const notRecorded: string[] = []
  for (const item of demand) {
    const name = item.skill.trim()
    if (!name) continue
    if (owned.has(name.toLowerCase())) {
      if (!matched.includes(name)) matched.push(name)
    } else if (!notRecorded.includes(name)) {
      notRecorded.push(name)
    }
  }
  return { matched, notRecorded }
}

export interface GapCoverage {
  matched: number
  total: number
}

export function gapCoverage(gap: SkillGap | null): GapCoverage {
  if (!gap) return { matched: 0, total: 0 }
  const total =
    gap.matched.length + gap.to_improve.length + gap.not_recorded.length
  return { matched: gap.matched.length, total }
}

export function profileFactSummary(data: ProfileData): string[] {
  const facts: string[] = []
  if (data.goals.target_role) {
    facts.push(`目标方向：${data.goals.target_role}`)
  }
  const education = [data.basic.education_level, data.basic.major]
    .map((item) => item.trim())
    .filter(Boolean)
    .join(' · ')
  if (education) facts.push(`教育背景：${education}`)
  if (data.basic.location) facts.push(`所在地：${data.basic.location}`)
  if (data.skills.length) facts.push(`已记录技能：${data.skills.length} 项`)
  if (data.projects.length) facts.push(`项目经历：${data.projects.length} 个`)
  if (data.experiences.length) {
    facts.push(`工作/实习经历：${data.experiences.length} 段`)
  }
  if (data.education.length) facts.push(`教育经历：${data.education.length} 段`)
  return facts
}

export function unknownInformation(data: ProfileData): string[] {
  const missing: string[] = []
  if (!data.goals.target_role.trim()) missing.push('目标岗位')
  if (!data.basic.education_level.trim()) missing.push('学历')
  if (!data.skills.length) missing.push('技能记录')
  if (data.skills.length && !data.skills.some((skill) => skill.evidence.trim())) {
    missing.push('技能证据')
  }
  if (!data.projects.length) missing.push('项目经历')
  if (!data.experiences.length) missing.push('工作/实习经历')
  return missing
}

export function formatProfileDate(value: string | null | undefined): string {
  if (!value) return '未记录'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}