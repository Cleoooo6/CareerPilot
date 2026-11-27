import type {
  Roadmap,
  RoadmapState,
  RoadmapSummaryList,
  RoadmapTaskUpdateResult,
  SkillGap,
  TaskStatus,
} from '@/types/roadmap'

import { requestJson } from './client'

export function getSkillGap(targetRole?: string): Promise<SkillGap> {
  const query = targetRole
    ? `?target_role=${encodeURIComponent(targetRole)}`
    : ''
  return requestJson<SkillGap>(`/api/roadmap/gap${query}`)
}

export function generateRoadmap(
  targetRole?: string,
  regenerate = false,
): Promise<Roadmap> {
  return requestJson<Roadmap>('/api/roadmap/generate', {
    method: 'POST',
    body: JSON.stringify({
      target_role: targetRole ?? null,
      regenerate,
    }),
  })
}

export function getCurrentRoadmap(): Promise<RoadmapState> {
  return requestJson<RoadmapState>('/api/roadmap/current')
}

export function listRoadmapDrafts(): Promise<RoadmapSummaryList> {
  return requestJson<RoadmapSummaryList>('/api/roadmap/drafts')
}

export function listRoadmapHistory(): Promise<RoadmapSummaryList> {
  return requestJson<RoadmapSummaryList>('/api/roadmap/history')
}

export function getRoadmap(roadmapId: string): Promise<Roadmap> {
  return requestJson<Roadmap>(`/api/roadmap/${roadmapId}`)
}

export function confirmRoadmap(roadmapId: string): Promise<Roadmap> {
  return requestJson<Roadmap>(`/api/roadmap/${roadmapId}/confirm`, {
    method: 'POST',
  })
}

export function discardRoadmap(roadmapId: string): Promise<unknown> {
  return requestJson<unknown>(`/api/roadmap/${roadmapId}/discard`, {
    method: 'POST',
  })
}

export function adjustRoadmap(roadmapId: string): Promise<Roadmap> {
  return requestJson<Roadmap>(`/api/roadmap/${roadmapId}/adjust`, {
    method: 'POST',
  })
}

export function updateRoadmapTask(
  taskId: string,
  status: TaskStatus,
  outcome?: string,
): Promise<RoadmapTaskUpdateResult> {
  return requestJson<RoadmapTaskUpdateResult>(`/api/roadmap/tasks/${taskId}`, {
    method: 'PATCH',
    body: JSON.stringify({ status, outcome: outcome ?? null }),
  })
}