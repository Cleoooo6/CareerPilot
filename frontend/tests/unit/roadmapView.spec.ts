import { describe, expect, it } from 'vitest'

import type { Roadmap, RoadmapTask } from '@/types/roadmap'
import {
  countTaskStatuses,
  flattenRoadmapTasks,
  marketSharePercent,
  progressPercent,
} from '@/utils/roadmapView'

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
    acceptance_criteria: '提交成果',
    status,
    completed_at: null,
    outcome: '',
    created_at: '2026-11-23T00:00:00Z',
    updated_at: '2026-11-23T00:00:00Z',
  }
}

describe('roadmap view helpers', () => {
  it('computes progress safely within 0-100', () => {
    expect(progressPercent(0, 0)).toBe(0)
    expect(progressPercent(4, 1)).toBe(25)
    expect(progressPercent(4, 5)).toBe(100)
  })

  it('counts task statuses', () => {
    const counts = countTaskStatuses([
      task('pending', '1'),
      task('in_progress', '2'),
      task('completed', '3'),
      task('completed', '4'),
    ])
    expect(counts.pending).toBe(1)
    expect(counts.in_progress).toBe(1)
    expect(counts.completed).toBe(2)
    expect(counts.abandoned).toBe(0)
  })

  it('flattens tasks from all stages', () => {
    const roadmap = {
      stages: [
        { tasks: [task('pending', '1'), task('pending', '2')] },
        { tasks: [task('completed', '3')] },
      ],
    } as Roadmap
    expect(flattenRoadmapTasks(roadmap).map((item) => item.id)).toEqual([
      '1',
      '2',
      '3',
    ])
    expect(flattenRoadmapTasks(null)).toEqual([])
  })

  it('renders market share as a whole percentage', () => {
    expect(
      marketSharePercent({
        name: 'Python',
        market_count: 4,
        market_share: 0.6667,
        priority: 'high',
        reason: '',
      }),
    ).toBe(67)
  })
})