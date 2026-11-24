import { expect, fileUser, test, userHeaders } from './fixtures'

const USER = fileUser('consistency')
test.use({ extraHTTPHeaders: { 'X-User-Id': USER } })

const PROFILE = {
  basic: {
    name: '一致性测试用户',
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
      id: 'consistency-python',
      name: 'Python',
      proficiency: '熟练',
      evidence: '课程项目',
      category: '编程语言',
    },
    {
      id: 'consistency-sql',
      name: 'SQL',
      proficiency: '',
      evidence: '',
      category: '数据工具',
    },
  ],
  education: [],
  projects: [],
  experiences: [],
}

test.beforeAll(async ({ request }) => {
  const headers = userHeaders(USER)
  const profile = await request.put('/api/profile', {
    data: { data: PROFILE },
    headers,
  })
  expect(profile.ok()).toBeTruthy()

  const current = await request.get('/api/roadmap/current', { headers })
  const currentBody = (await current.json()) as {
    data: { roadmap: { id: string } | null }
  }
  if (!currentBody.data.roadmap) {
    const generated = await request.post('/api/roadmap/generate', {
      data: {},
      headers,
    })
    const body = (await generated.json()) as { data: { id: string } }
    const confirmed = await request.post(
      `/api/roadmap/${body.data.id}/confirm`,
      { headers },
    )
    expect(confirmed.ok()).toBeTruthy()
  }
})

test('Profile and Roadmap share the same gap totals, share and labels', async ({
  page,
  request,
}) => {
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))

  const marketResponse = await request.get(
    '/api/market/skills?role=数据分析师&limit=20',
    { headers: userHeaders(USER) },
  )
  const market = (await marketResponse.json()) as {
    data: { items: Array<{ skill: string; count: number; share: number }> }
  }
  const gapResponse = await request.get('/api/roadmap/gap', {
    headers: userHeaders(USER),
  })
  const gap = (await gapResponse.json()) as {
    data: {
      matched: unknown[]
      to_improve: unknown[]
      not_recorded: unknown[]
    }
  }
  const total =
    gap.data.matched.length +
    gap.data.to_improve.length +
    gap.data.not_recorded.length
  const marketItems = new Map(
    market.data.items.map((item) => [item.skill, item]),
  )
  const python = marketItems.get('Python')
  expect(python).toBeTruthy()
  expect(total).toBe(market.data.items.length)

  await page.goto('/profile?tab=market')
  const coverage = page.getByTestId('profile-gap-coverage')
  await expect(coverage).toContainText(
    `目标岗位需求技能已记录 ${gap.data.matched.length} / ${total}`,
    { timeout: 10_000 },
  )

  await page.goto('/roadmap')
  const gapCard = page.getByTestId('roadmap-gap')
  const expand = gapCard.locator('button.link-button')
  if (await expand.count()) {
    await expect(expand).toContainText(`展开全部 ${total} 项`)
    await expand.click()
    await expect(expand).toHaveText('收起')
  }
  await expect(gapCard.locator('.gap-table tbody tr')).toHaveCount(total)
  const pythonRow = gapCard
    .locator('.gap-table tbody tr')
    .filter({ hasText: 'Python' })
  await expect(pythonRow).toContainText(`${Math.round(python!.share * 100)}%`)

  await page.goto('/profile?tab=growth')
  await expect(page.getByText(/当前路线 v\d+/)).toBeVisible()
  await expect(page.getByRole('heading', { name: '资料版本' })).toBeVisible()

  await page.goto('/roadmap')
  await page.getByTestId('roadmap-history').click()
  await expect(page.locator('.drawer')).toContainText('可能跳号')

  expect(pageErrors).toEqual([])
})