import { describe, expect, it } from 'vitest'

import type { ProfileData } from '@/types/profile'
import type { Roadmap, RoadmapTask } from '@/types/roadmap'
import {
  currentStage,
  dashboardGreeting,
  formatDashboardDate,
  nextTasks,
  profileCompletion,
  topCountTitle,
} from '@/utils/dashboardView'

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

function task(
  status: RoadmapTask['status'],
  id: string,
): RoadmapTask {
  return {
    id,
    stage_id: 'stage-1',
    position: 1,
    title: `任务 ${id}`,
    description: '',
    task_type: 'learning',
    priority: 'medium',
    estimated_time: '',
    acceptance_criteria: '',
    status,
    completed_at: null,
    outcome: '',
    created_at: '2026-11-24T00:00:00Z',
    updated_at: '2026-11-24T00:00:00Z',
  }
}

describe('dashboard view helpers', () => {
  it('computes completion only from confirmed profile fields', () => {
    expect(profileCompletion(null)).toBe(0)
    expect(profileCompletion(emptyData())).toBe(0)

    const partial = emptyData({
      basic: {
        name: '林小舟',
        education_level: '本科',
        major: '信息管理',
        graduation_year: 2026,
        location: '上海',
      },
      goals: {
        target_role: '数据分析师',
        target_industry: '互联网',
        job_status: '求职中',
        desired_direction: '数据分析',
      },
      skills: [
        {
          id: 's1',
          name: 'Python',
          proficiency: '熟练',
          evidence: '课程项目',
          category: '编程语言',
          source: 'manual',
          verification: 'confirmed',
          updated_at: '2026-11-24',
        },
      ],
    })
    expect(profileCompletion(partial)).toBe(77)

    const full = emptyData({
      basic: partial.basic,
      goals: partial.goals,
      skills: partial.skills,
      education: [
        {
          id: 'e1',
          school: '示例大学',
          degree: '本科',
          major: '信息管理',
          start_date: '',
          end_date: '',
          description: '',
        },
      ],
      projects: [
        {
          id: 'p1',
          name: '示例项目',
          role: '',
          description: '',
          tech_stack: '',
          achievements: '',
          start_date: '',
          end_date: '',
        },
      ],
      experiences: [
        {
          id: 'x1',
          company: '示例公司',
          position: '',
          start_date: '',
          end_date: '',
          description: '',
        },
      ],
    })
    expect(profileCompletion(full)).toBe(100)
  })

  it('only claims Top 3 when three items exist', () => {
    expect(topCountTitle('能力差距', 1)).toBe('能力差距（1 项）')
    expect(topCountTitle('能力差距', 2)).toBe('能力差距（2 项）')
    expect(topCountTitle('能力差距', 3)).toBe('能力差距 Top 3')
    expect(topCountTitle('能力差距', 0)).toBe('能力差距')
  })

  it('uses honest greeting and date labels', () => {
    expect(dashboardGreeting(new Date(2026, 10, 24, 9))).toBe('早上好')
    expect(dashboardGreeting(new Date(2026, 10, 24, 13))).toBe('中午好')
    expect(dashboardGreeting(new Date(2026, 10, 24, 16))).toBe('下午好')
    expect(dashboardGreeting(new Date(2026, 10, 24, 21))).toBe('晚上好')
    expect(formatDashboardDate(new Date(2026, 10, 24))).toContain('11月')
    expect(formatDashboardDate(new Date(2026, 10, 24))).toContain('24')
  })

  it('selects pending tasks without inventing progress', () => {
    const tasks = [
      task('completed', '1'),
      task('pending', '2'),
      task('in_progress', '3'),
      task('abandoned', '4'),
      task('pending', '5'),
    ]
    expect(nextTasks(tasks, 2).map((item) => item.id)).toEqual(['2', '3'])
    expect(nextTasks(tasks).map((item) => item.id)).toEqual(['2', '3', '5'])
  })

  it('picks the stage containing the next actionable task', () => {
    const roadmap = {
      stages: [
        { id: 's1', tasks: [task('completed', '1')] },
        { id: 's2', tasks: [task('in_progress', '2')] },
        { id: 's3', tasks: [task('pending', '3')] },
      ],
    } as Roadmap
    expect(currentStage(roadmap)?.id).toBe('s2')
    expect(currentStage(null)).toBeNull()
  })
})