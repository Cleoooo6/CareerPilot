import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { createSession, expect, test } from './fixtures'

const DOCX_MIME =
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
const RESUME = readFileSync(
  join(process.cwd(), 'e2e', 'fixtures', 'fictional-resume.docx'),
)

const PROFILE = {
  basic: {
    name: '阶段C用户',
    education_level: '本科',
    major: '信息管理与信息系统',
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
      id: 'pc-python',
      name: 'Python',
      proficiency: '熟练',
      evidence: '课程项目',
      category: '编程语言',
    },
  ],
  education: [],
  projects: [],
  experiences: [],
}

test('phase C private endpoints reject anonymous requests', async ({ request }) => {
  const sampleId = '00000000-0000-0000-0000-000000000001'
  const cases: Array<[string, string]> = [
    ['GET', `/api/profile/resume/${sampleId}`],
    ['POST', `/api/profile/resume/${sampleId}/reparse`],
    ['POST', '/api/profile/analysis'],
    ['POST', `/api/roadmap/${sampleId}/adjust`],
  ]
  for (const [method, path] of cases) {
    const response = await request.fetch(path, { method })
    expect(response.status(), `${method} ${path}`).toBe(401)
  }
})

test('phase C resume/profile/roadmap chain is isolated between two real users', async ({
  browser,
}) => {
  const contextA = await browser.newContext()
  const userA = await createSession(contextA.request, 'pc-a')
  const csrfA = { 'X-CSRF-Token': userA.user.csrfToken }

  const uploaded = await contextA.request.post('/api/profile/resume/upload', {
    headers: csrfA,
    multipart: {
      file: { name: 'resume.docx', mimeType: DOCX_MIME, buffer: RESUME },
    },
  })
  expect(uploaded.status()).toBe(201)
  const resumeId = ((await uploaded.json()) as { data: { id: string } }).data.id

  const reparsed = await contextA.request.post(
    `/api/profile/resume/${resumeId}/reparse`,
    { headers: csrfA },
  )
  expect(reparsed.status()).toBe(200)
  expect(((await reparsed.json()) as { data: { id: string } }).data.id).toBe(
    resumeId,
  )

  const savedProfile = await userA.api.put('/api/profile', {
    data: PROFILE,
  })
  expect(savedProfile.ok()).toBeTruthy()

  const firstAnalysis = await userA.api.post('/api/profile/analysis', {})
  expect(firstAnalysis.ok()).toBeTruthy()
  const firstId = ((await firstAnalysis.json()) as { data: { id: string } }).data
    .id
  const reusedAnalysis = await userA.api.post('/api/profile/analysis', {})
  expect(
    ((await reusedAnalysis.json()) as { data: { id: string } }).data.id,
  ).toBe(firstId)

  const forcedAnalysis = await userA.api.post('/api/profile/analysis', {
    force: true,
  })
  expect(forcedAnalysis.ok()).toBeTruthy()
  expect(
    ((await forcedAnalysis.json()) as { data: { id: string } }).data.id,
  ).not.toBe(firstId)

  const updatedProfile = {
    ...PROFILE,
    basic: { ...PROFILE.basic, name: '阶段C用户已更新' },
  }
  expect(
    (await userA.api.put('/api/profile', { data: updatedProfile })).ok(),
  ).toBeTruthy()
  const analyses = await userA.api.get('/api/profile/analysis')
  const items = (
    (await analyses.json()) as {
      data: { items: Array<{ stale: boolean }> }
    }
  ).data.items
  expect(items[0].stale).toBe(true)

  const generated = await userA.api.post('/api/roadmap/generate', {})
  expect(generated.ok()).toBeTruthy()
  const roadmapId = ((await generated.json()) as { data: { id: string } }).data
    .id
  expect(
    (await userA.api.post(`/api/roadmap/${roadmapId}/confirm`, {})).ok(),
  ).toBeTruthy()

  const current = await userA.api.get('/api/roadmap/current')
  const roadmap = (
    (await current.json()) as {
      data: {
        roadmap: {
          stages: Array<{ tasks: Array<{ id: string; title: string }> }>
        }
      }
    }
  ).data.roadmap
  const firstTask = roadmap.stages[0].tasks[0]
  expect(
    (
      await userA.api.patch(`/api/roadmap/tasks/${firstTask.id}`, {
        status: 'completed',
        outcome: '已完成并记录',
      })
    ).ok(),
  ).toBeTruthy()

  const adjusted = await userA.api.post(`/api/roadmap/${roadmapId}/adjust`, {})
  expect(adjusted.ok()).toBeTruthy()
  const draft = (
    (await adjusted.json()) as {
      data: {
        id: string
        status: string
        stages: Array<{ tasks: Array<{ title: string; status: string }> }>
      }
    }
  ).data
  expect(draft.id).not.toBe(roadmapId)
  expect(draft.status).toBe('draft')
  const draftTasks = draft.stages.flatMap((stage) => stage.tasks)
  expect(
    draftTasks.some(
      (task) =>
        task.title === firstTask.title && task.status === 'completed',
    ),
  ).toBe(true)

  const contextB = await browser.newContext()
  const userB = await createSession(contextB.request, 'pc-b')
  const csrfB = { 'X-CSRF-Token': userB.user.csrfToken }

  const bProfile = await userB.api.get('/api/profile')
  expect(
    ((await bProfile.json()) as { data: { profile: unknown } }).data.profile,
  ).toBeNull()

  expect(
    (await userB.api.get(`/api/profile/resume/${resumeId}`)).status(),
  ).toBe(404)
  expect(
    (
      await contextB.request.post(
        `/api/profile/resume/${resumeId}/reparse`,
        { headers: csrfB },
      )
    ).status(),
  ).toBe(404)
  expect((await userB.api.get(`/api/roadmap/${roadmapId}`)).status()).toBe(404)
  const crossAdjust = await contextB.request.post(
    `/api/roadmap/${roadmapId}/adjust`,
    { headers: csrfB },
  )
  // 409「当前没有正式路线可调整」与 404 一样拒绝跨用户操作，且不泄露 A 的资源。
  expect([404, 409]).toContain(crossAdjust.status())
  const bCurrent = await userB.api.get('/api/roadmap/current')
  expect(
    ((await bCurrent.json()) as { data: { roadmap: unknown } }).data.roadmap,
  ).toBeNull()

  await contextA.close()
  await contextB.close()
})