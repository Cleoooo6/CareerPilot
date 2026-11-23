import type {
  Roadmap,
  RoadmapTask,
  SkillGapItem,
  TaskStatus,
} from '@/types/roadmap'

export function progressPercent(total: number, completed: number): number {
  if (total <= 0) return 0
  return Math.min(100, Math.max(0, Math.round((completed / total) * 100)))
}

export function countTaskStatuses(
  tasks: RoadmapTask[],
): Record<TaskStatus, number> {
  const counts: Record<TaskStatus, number> = {
    pending: 0,
    in_progress: 0,
    completed: 0,
    abandoned: 0,
  }
  for (const task of tasks) {
    counts[task.status] += 1
  }
  return counts
}

export function flattenRoadmapTasks(roadmap: Roadmap | null): RoadmapTask[] {
  if (!roadmap) return []
  return roadmap.stages.flatMap((stage) => stage.tasks)
}

export function marketSharePercent(item: SkillGapItem): number {
  return Math.round(item.market_share * 100)
}

export function formatRoadmapDate(value: string | null | undefined): string {
  if (!value) return '未记录'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}