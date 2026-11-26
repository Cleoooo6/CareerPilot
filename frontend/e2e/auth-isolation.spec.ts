import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import {
  createSession,
  expect,
  fileUser,
  test,

  type Page,
} from './fixtures'

const E2E_PASSWORD = 'E2ePassword123'

const PROFILE_FOR_A = {
  basic: {
    name: '隔离用户A',
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
      id: 'iso-python',
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

const resumeBuffer = readFileSync(
  join(process.cwd(), 'e2e', 'fixtures', 'fictional-resume.docx'),
)


async function forgeUserHeaderHeaders(user: { ref: string }) {
  return { 'X-User-Id': user.ref }
}

test('unauthenticated private APIs return 401 even with forged headers', async ({
  request,
}) => {
  const profile = await request.get('/api/profile')
  expect(profile.status()).toBe(401)

  const me = await request.get('/api/auth/me', {
    headers: { 'X-User-Id': 'attacker' },
  })
  expect(me.status()).toBe(401)

  const conversations = await request.get('/api/conversations', {
    headers: { 'X-User-Id': 'attacker' },
  })
  expect(conversations.status()).toBe(401)

  const sse = await request.post(
    '/api/conversations/00000000-0000-0000-0000-000000000000/messages',
    {
      data: { content: '未认证' },
      headers: { 'X-User-Id': 'attacker' },
    },
  )
  expect(sse.status()).toBe(401)

  const upload = await request.post('/api/profile/resume/upload', {
    headers: { 'X-User-Id': 'attacker' },
    multipart: {
      file: {
        name: 'attacker.docx',
        mimeType:
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        buffer: resumeBuffer,
      },
    },
  })
  expect(upload.status()).toBe(401)
})

test('two real users cannot read or mutate each other resources', async ({
  browser,
}) => {
  const contextA = await browser.newContext()
  const userA = await createSession(contextA.request, 'iso-a')

  const saveProfile = await userA.api.put('/api/profile', {
    data: PROFILE_FOR_A,
  })
  expect(saveProfile.ok()).toBeTruthy()

  const conversation = await userA.api.post('/api/conversations', {
    title: 'A 专属对话',
  })
  expect(conversation.ok()).toBeTruthy()
  const conversationId = (
    (await conversation.json()) as { data: { id: string } }
  ).data.id

  const upload = await contextA.request.post('/api/profile/resume/upload', {
    headers: { 'X-CSRF-Token': userA.user.csrfToken },
    multipart: {
      file: {
        name: 'a-resume.docx',
        mimeType:
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        buffer: resumeBuffer,
      },
    },
  })
  expect(upload.ok()).toBeTruthy()
  const resumeId = ((await upload.json()) as { data: { id: string } }).data.id

  const contextB = await browser.newContext()
  const userB = await createSession(contextB.request, 'iso-b')

  const bProfile = await userB.api.get('/api/profile')
  expect(
    ((await bProfile.json()) as { data: { profile: unknown } }).data.profile,
  ).toBeNull()

  const bConversations = await userB.api.get('/api/conversations')
  expect(
    ((await bConversations.json()) as { data: { items: unknown[] } }).data
      .items,
  ).toEqual([])

  const crossRead = await userB.api.get(`/api/conversations/${conversationId}`)
  expect(crossRead.status()).toBe(404)

  const crossMessages = await userB.api.get(
    `/api/conversations/${conversationId}/messages`,
  )
  expect(crossMessages.status()).toBe(404)

  const crossSse = await userB.api.post(
    `/api/conversations/${conversationId}/messages`,
    { content: '越权消息' },
  )
  expect(crossSse.status()).toBe(404)

  const crossResumeRead = await userB.api.get(`/api/profile/resume/${resumeId}`)
  expect(crossResumeRead.status()).toBe(404)

  const crossResumeDiscard = await userB.api.post(
    `/api/profile/resume/${resumeId}/discard`,
  )
  expect(crossResumeDiscard.status()).toBe(404)

  const forgedConversations = await contextB.request.get('/api/conversations', {
    headers: await forgeUserHeaderHeaders(userA.user),
  })
  expect(
    ((await forgedConversations.json()) as { data: { items: unknown[] } }).data
      .items,
  ).toEqual([])

  await contextA.close()
  await contextB.close()
})

test('logout and logout-all revoke sessions immediately', async ({ browser }) => {
  const context = await browser.newContext()
  const session = await createSession(context.request, 'iso-logout')

  const logout = await session.api.post('/api/auth/logout')
  expect(logout.ok()).toBeTruthy()
  const me = await context.request.get('/api/auth/me')
  expect(me.status()).toBe(401)

  const relogin = await context.request.post('/api/auth/login', {
    data: { email: session.user.email, password: E2E_PASSWORD },
  })
  expect(relogin.ok()).toBeTruthy()
  const newCsrf = (
    (await relogin.json()) as { data: { csrf_token: string } }
  ).data.csrf_token

  const secondContext = await browser.newContext()
  const secondLogin = await secondContext.request.post('/api/auth/login', {
    data: { email: session.user.email, password: E2E_PASSWORD },
  })
  expect(secondLogin.ok()).toBeTruthy()

  const logoutAll = await context.request.post('/api/auth/logout-all', {
    headers: { 'X-CSRF-Token': newCsrf },
  })
  expect(logoutAll.ok()).toBeTruthy()

  const meAfterAll = await context.request.get('/api/auth/me')
  expect(meAfterAll.status()).toBe(401)
  const secondMe = await secondContext.request.get('/api/auth/me')
  expect(secondMe.status()).toBe(401)

  await context.close()
  await secondContext.close()
})

test('a freshly registered user starts with an empty workspace', async ({
  browser,
}) => {
  const context = await browser.newContext()
  const session = await createSession(context.request, 'iso-fresh')

  const profile = await session.api.get('/api/profile')
  expect(
    ((await profile.json()) as { data: { profile: unknown } }).data.profile,
  ).toBeNull()

  const conversations = await session.api.get('/api/conversations')
  expect(
    ((await conversations.json()) as { data: { items: unknown[] } }).data.items,
  ).toEqual([])

  const resumes = await session.api.get('/api/profile/resume')
  expect(
    ((await resumes.json()) as { data: { items: unknown[] } }).data.items,
  ).toEqual([])

  const roadmap = await session.api.get('/api/roadmap/current')
  expect(
    ((await roadmap.json()) as { data: { roadmap: unknown } }).data.roadmap,
  ).toBeNull()

  await context.close()
})

test('login and register work through the real UI and logout returns to login', async ({
  browser,
}) => {
  const context = await browser.newContext()
  const seed = await createSession(context.request, 'ui-flow')
  const logout = await seed.api.post('/api/auth/logout')
  expect(logout.ok()).toBeTruthy()

  const page: Page = await context.newPage()

  await page.goto('/login')
  await page.getByLabel('邮箱').fill(seed.user.email)
  await page.getByLabel('密码').fill(E2E_PASSWORD)
  await page.getByRole('button', { name: '登录', exact: true }).click()
  await expect(page).toHaveURL(/\/dashboard/)
  await expect(
    page.getByRole('button', { name: '退出', exact: true }),
  ).toBeVisible()

  await page.getByRole('button', { name: '退出', exact: true }).click()
  await expect(page).toHaveURL(/\/login/)

  const freshEmail = `${fileUser('ui-register')}@e2e.careerpilot.test`
  await page.goto('/register')
  await page.getByLabel('邮箱').fill(freshEmail)
  await page.getByLabel('昵称（可选）').fill('E2E 新用户')
  await page.getByLabel('密码', { exact: true }).fill(E2E_PASSWORD)
  await page.getByLabel('确认密码').fill(E2E_PASSWORD)
  await page.getByRole('button', { name: '创建账号' }).click()
  await expect(page).toHaveURL(/\/dashboard/)
  await expect(page.getByText('E2E 新用户')).toBeVisible()

  await context.close()
})