import type {
  ProfileAnalysisListOut,
  ProfileAnalysisOut,
  ProfileData,
  ProfileOut,
  ProfileRevisionListOut,
  ProfileSection,
  ProfileStateOut,
  ResumeParseListOut,
  ResumeParseOut,
} from '@/types/profile'

import { requestForm, requestJson } from './client'

export function getProfile(): Promise<ProfileStateOut> {
  return requestJson<ProfileStateOut>('/api/profile')
}

export function saveProfile(data: ProfileData): Promise<ProfileOut> {
  return requestJson<ProfileOut>('/api/profile', {
    method: 'PUT',
    body: JSON.stringify({ data }),
  })
}

export function deleteProfile(): Promise<void> {
  return requestJson<void>('/api/profile', { method: 'DELETE' })
}

export function listResumes(): Promise<ResumeParseListOut> {
  return requestJson<ResumeParseListOut>('/api/profile/resume')
}

export function uploadResume(file: File): Promise<ResumeParseOut> {
  const form = new FormData()
  form.append('file', file)
  return requestForm<ResumeParseOut>('/api/profile/resume/upload', form)
}

export function updateResume(
  resumeId: string,
  data: ProfileData,
): Promise<ResumeParseOut> {
  return requestJson<ResumeParseOut>(`/api/profile/resume/${resumeId}`, {
    method: 'PATCH',
    body: JSON.stringify({ parsed_data: data }),
  })
}

export function confirmResume(
  resumeId: string,
  data: ProfileData,
  sections: ProfileSection[],
): Promise<ProfileOut> {
  return requestJson<ProfileOut>(`/api/profile/resume/${resumeId}/confirm`, {
    method: 'POST',
    body: JSON.stringify({ sections, draft: data }),
  })
}

export function discardResume(resumeId: string): Promise<ResumeParseOut> {
  return requestJson<ResumeParseOut>(`/api/profile/resume/${resumeId}/discard`, {
    method: 'POST',
  })
}

export function reparseResume(resumeId: string): Promise<ResumeParseOut> {
  return requestJson<ResumeParseOut>(
    `/api/profile/resume/${resumeId}/reparse`,
    { method: 'POST' },
  )
}

export function analyzeProfile(force = false): Promise<ProfileAnalysisOut> {
  return requestJson<ProfileAnalysisOut>('/api/profile/analysis', {
    method: 'POST',
    body: JSON.stringify({ force }),
  })
}

export function listAnalyses(): Promise<ProfileAnalysisListOut> {
  return requestJson<ProfileAnalysisListOut>('/api/profile/analysis')
}
export function listProfileRevisions(): Promise<ProfileRevisionListOut> {
  return requestJson<ProfileRevisionListOut>('/api/profile/revisions')
}