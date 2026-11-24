import { describe, expect, it } from 'vitest'

import type { ProfileAnalysisOut, ProfileData, SkillItem } from '@/types/profile'
import type { SkillGap } from '@/types/roadmap'
import {
  UNCATEGORIZED_SKILL,
  gapCoverage,
  groupSkills,
  latestAnalysis,
  marketSkillGap,
  proficiencyLabel,
  profileFactSummary,
  sourceLabel,
  unknownInformation,
  verificationLabel,
} from '@/utils/profileView'

function skill(overrides: Partial<SkillItem> = {}): SkillItem {
  return {
    id: 's1',
    name: 'Python',
    proficiency: '熟练',
    evidence: '课程项目',
    category: '编程语言',
    source: 'manual',
    verification: 'confirmed',
    updated_at: '2026-11-23',
    ...overrides,
  }
}

function emptyData(overrides: Partial<ProfileData> = {}): ProfileData {
  return {
    basic: {
      name: '',
      education_level: '',
      major: '',
      graduation_year: null,
      location: '',
    },
    goals: {
      target_role: '',
      target_industry: '',
      job_status: '',
      desired_direction: '',
    },
    skills: [],
    education: [],
    projects: [],
    experiences: [],
    ...overrides,
  }
}

describe('profile view helpers', () => {
  it('groups skills by category and keeps uncategorized ones explicit', () => {
    const groups = groupSkills([
      skill(),
      skill({ id: 's2', name: 'SQL', category: '数据工具' }),
      skill({ id: 's3', name: '沟通', category: '' }),
    ])
    expect(groups.map((group) => group.category)).toEqual([
      '编程语言',
      '数据工具',
      UNCATEGORIZED_SKILL,
    ])
    expect(groups[0].skills).toHaveLength(1)
  })

  it('never invents ability levels or provenance when data is missing', () => {
    expect(proficiencyLabel('')).toBe('待评估')
    expect(proficiencyLabel('   ')).toBe('待评估')
    expect(sourceLabel('')).toBe('来源未记录')
    expect(sourceLabel('resume')).toBe('简历导入')
    expect(verificationLabel('')).toBe('待确认')
    expect(verificationLabel('confirmed')).toBe('资料已确认')
  })

  it('compares recorded skills with market demand without scoring ability', () => {
    const gap = marketSkillGap(
      [skill(), skill({ id: 's2', name: 'SQL' })],
      [{ skill: 'python' }, { skill: 'SQL' }, { skill: 'SQL' }, { skill: 'Spark' }],
    )
    expect(gap.matched).toEqual(['python', 'SQL'])
    expect(gap.notRecorded).toEqual(['Spark'])
  })

  it('builds fact-only profile summaries', () => {
    const data = emptyData({
      basic: {
        name: '张三',
        education_level: '本科',
        major: '信息管理',
        graduation_year: 2026,
        location: '上海',
      },
      goals: {
        target_role: '数据分析师',
        target_industry: '',
        job_status: '',
        desired_direction: '',
      },
      skills: [skill()],
      projects: [{} as ProfileData['projects'][number]],
    })
    const facts = profileFactSummary(data)
    expect(facts).toContain('目标方向：数据分析师')
    expect(facts).toContain('教育背景：本科 · 信息管理')
    expect(facts).toContain('已记录技能：1 项')
    expect(facts).toContain('项目经历：1 个')
  })

  it('lists unknown information instead of filling gaps', () => {
    const data = emptyData({ skills: [skill({ evidence: '' })] })
    const missing = unknownInformation(data)
    expect(missing).toContain('目标岗位')
    expect(missing).toContain('学历')
    expect(missing).toContain('技能证据')
    expect(missing).toContain('项目经历')
  })

  it('derives coverage from the shared roadmap gap payload', () => {
    const gap = {
      matched: [
        { name: 'Python', market_count: 4, market_share: 0.6667, priority: 'low', reason: '' },
      ],
      to_improve: [
        { name: 'SQL', market_count: 5, market_share: 0.8333, priority: 'low', reason: '' },
      ],
      not_recorded: [
        { name: 'Excel', market_count: 3, market_share: 0.5, priority: 'high', reason: '' },
      ],
    } as SkillGap
    expect(gapCoverage(gap)).toEqual({ matched: 1, total: 3 })
    expect(gapCoverage(null)).toEqual({ matched: 0, total: 0 })
  })

  it('always selects the newest analysis by created_at', () => {
    const analyses = [
      { id: 'old', created_at: '2026-11-20T10:00:00Z' },
      { id: 'new', created_at: '2026-11-23T10:00:00Z' },
    ] as ProfileAnalysisOut[]
    expect(latestAnalysis(analyses)?.id).toBe('new')
    expect(latestAnalysis([])).toBeNull()
  })
})