import type { MarketCountItem } from '@/types/market'
import type { ProfileData } from '@/types/profile'
import type { Roadmap, RoadmapStage, RoadmapTask } from '@/types/roadmap'

export function profileCompletion(data: ProfileData | null): number {
  if (!data) return 0
  const checks = [
    Boolean(data.basic.name.trim()),
    Boolean(data.basic.education_level.trim()),
    Boolean(data.basic.major.trim()),
    Boolean(data.basic.graduation_year),
    Boolean(data.basic.location.trim()),
    Boolean(data.goals.target_role.trim()),
    Boolean(data.goals.target_industry.trim()),
    Boolean(data.goals.job_status.trim()),
    Boolean(data.goals.desired_direction.trim()),
    data.skills.length > 0,
    data.education.length > 0,
    data.projects.length > 0,
    data.experiences.length > 0,
  ]
  return Math.round((checks.filter(Boolean).length / checks.length) * 100)
}

export function dashboardGreeting(date = new Date()): string {
  const hour = date.getHours()
  if (hour < 11) return '早上好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
}

export function formatDashboardDate(date = new Date()): string {
  return date.toLocaleDateString('zh-CN', {
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  })
}

export function nextTasks(
  tasks: RoadmapTask[],
  limit = 3,
): RoadmapTask[] {
  return tasks
    .filter((task) => task.status === 'pending' || task.status === 'in_progress')
    .slice(0, limit)
}

export function topCountTitle(
  base: string,
  count: number,
  max = 3,
): string {
  if (count <= 0) return base
  if (count >= max) return `${base} Top ${max}`
  return `${base}（${count} 项）`
}

export function currentStage(roadmap: Roadmap | null): RoadmapStage | null {
  if (!roadmap || !roadmap.stages.length) return null
  return (
    roadmap.stages.find((stage) =>
      stage.tasks.some(
        (task) => task.status === 'pending' || task.status === 'in_progress',
      ),
    ) ?? roadmap.stages[roadmap.stages.length - 1]
  )
}
export function hasRealMarketData(datasetKinds: string[]): boolean {
  return datasetKinds.includes('real')
}

export function pickMarketRole(
  roles: MarketCountItem[],
  targetRole: string,
  hasRealData: boolean,
): MarketCountItem | null {
  const normalized = targetRole.trim()
  // 没有用户目标岗位或没有真实样本时，绝不展示演示/全局热门岗位。
  if (!normalized || !hasRealData) return null
  return roles.find((item) => item.name === normalized) ?? null
}