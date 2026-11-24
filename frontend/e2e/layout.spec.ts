import { expect, fileUser, test, userHeaders, type Page } from './fixtures'

const USER = fileUser('layout')
test.use({ extraHTTPHeaders: { 'X-User-Id': USER } })

const PROFILE = {
  basic: {
    name: '布局测试用户',
    education_level: '硕士',
    major: '信息管理与信息系统',
    graduation_year: 2025,
    location: '上海',
  },
  goals: {
    target_role: '数据分析师',
    target_industry: '互联网',
    job_status: '求职中',
    desired_direction: '数据分析与数据产品',
  },
  skills: [
    { id: 'layout-s1', name: 'Python', proficiency: '熟练', evidence: '数据分析项目', category: '编程语言' },
    { id: 'layout-s2', name: 'SQL', proficiency: '熟练', evidence: '业务取数与看板', category: '数据工具' },
    { id: 'layout-s3', name: 'Tableau', proficiency: '熟悉', evidence: '可视化看板', category: '数据工具' },
    { id: 'layout-s4', name: 'Spark', proficiency: '了解', evidence: '课程实验', category: '大数据' },
    { id: 'layout-s5', name: '统计学', proficiency: '熟练', evidence: 'A/B 测试项目', category: '分析方法' },
    { id: 'layout-s6', name: '项目管理', proficiency: '熟悉', evidence: '跨团队协作', category: '通用能力' },
  ],
  education: [
    { id: 'layout-e1', school: '示例大学', degree: '硕士', major: '信息管理', start_date: '2022-09', end_date: '2025-06', description: '' },
    { id: 'layout-e2', school: '示例学院', degree: '本科', major: '统计学', start_date: '2018-09', end_date: '2022-06', description: '' },
  ],
  projects: [
    { id: 'layout-p1', name: '零售经营分析', role: '数据分析', description: '搭建经营指标与看板，支持门店复盘。', tech_stack: 'SQL, Python, Tableau', achievements: '覆盖 30 家门店', start_date: '2024-03', end_date: '2024-08' },
    { id: 'layout-p2', name: '用户增长实验', role: '分析负责人', description: '设计 A/B 测试并评估转化效果。', tech_stack: 'Python, 统计学', achievements: '转化提升 8%', start_date: '2024-09', end_date: '2025-01' },
    { id: 'layout-p3', name: '数据质量巡检', role: '开发者', description: '建立数据质量规则与异常告警。', tech_stack: 'SQL, Python', achievements: '异常发现提前 1 天', start_date: '2025-02', end_date: '2025-05' },
  ],
  experiences: [
    { id: 'layout-x1', company: '示例科技', position: '数据分析实习生', start_date: '2024-03', end_date: '2024-08', description: '负责经营分析与看板维护。' },
    { id: 'layout-x2', company: '示例咨询', position: '研究助理', start_date: '2023-06', end_date: '2023-09', description: '参与行业研究与数据整理。' },
  ],
}

test.beforeAll(async ({ request }) => {
  const headers = userHeaders(USER)
  const profile = await request.put('/api/profile', {
    data: { data: PROFILE },
    headers,
  })
  expect(profile.ok()).toBeTruthy()

  const current = await request.get('/api/roadmap/current', { headers })
  expect(current.ok()).toBeTruthy()
  const currentBody = (await current.json()) as {
    data: { roadmap: { id: string } | null }
  }
  if (currentBody.data.roadmap) return

  const generated = await request.post('/api/roadmap/generate', {
    data: {},
    headers,
  })
  expect(generated.ok()).toBeTruthy()
  const generatedBody = (await generated.json()) as {
    data: { id: string }
  }
  const confirmed = await request.post(
    `/api/roadmap/${generatedBody.data.id}/confirm`,
    { headers },
  )
  expect(confirmed.ok()).toBeTruthy()
})

async function assertNaturalScroll(page: Page) {
  await page.waitForTimeout(300)
  const viewport = page.viewportSize()
  expect(viewport).not.toBeNull()
  const height = await page.evaluate(
    () => document.documentElement.scrollHeight,
  )
  expect(height).toBeGreaterThan(viewport!.height)

  await page.mouse.move(
    Math.floor(viewport!.width / 2),
    Math.floor(viewport!.height / 2),
  )
  await page.mouse.wheel(0, 1400)
  await page.waitForTimeout(350)
  expect(await page.evaluate(() => window.scrollY)).toBeGreaterThan(0)

  const nested = await page.evaluate(() =>
    Array.from(document.querySelectorAll('.app-main *'))
      .filter((node) => {
        const element = node as HTMLElement
        if (['INPUT', 'TEXTAREA', 'SELECT'].includes(element.tagName)) {
          return false
        }
        const style = getComputedStyle(element)
        return (
          (style.overflowY === 'auto' || style.overflowY === 'scroll') &&
          element.scrollHeight > element.clientHeight + 4
        )
      })
      .map((node) => (node as HTMLElement).className),
  )
  expect(nested).toEqual([])

  for (const selector of ['.app-main', '.page']) {
    const overflow = await page
      .locator(selector)
      .evaluate((element) => getComputedStyle(element).overflowY)
    expect(['visible', 'clip', 'hidden']).toContain(overflow)
  }
}

test('profile page scrolls naturally from the page body', async ({ page }) => {
  await page.goto('/profile')
  await expect(page.getByRole('heading', { level: 2, name: /Profile/ })).toBeVisible()
  await expect(page.getByRole('heading', { name: '基本信息' })).toBeVisible()
  await page.waitForLoadState('networkidle')
  await assertNaturalScroll(page)
})

test('market page scrolls naturally from the page body', async ({ page }) => {
  await page.goto('/market')
  await expect(page.locator('.market-meta')).toBeVisible()
  await page.waitForLoadState('networkidle')
  await assertNaturalScroll(page)
})

test('roadmap page scrolls naturally from the page body', async ({ page }) => {
  await page.goto('/roadmap')
  await expect(page.getByTestId('roadmap-current')).toBeVisible()
  await page.waitForLoadState('networkidle')
  await assertNaturalScroll(page)
})

test('dashboard renders the single focus card without fake metrics', async ({
  page,
  request,
}) => {
  await page.goto('/dashboard')
  await expect(page.getByRole('heading', { level: 2, name: /Dashboard/ })).toBeVisible()
  await expect(page.locator('.dash-focus')).toBeVisible()
  await expect(page.locator('.dash-metric-ring')).toContainText('%')
  await expect(page.locator('.dash-metric-link')).toHaveAttribute(
    'href',
    /\/profile/,
  )

  const gapResponse = await request.get('/api/roadmap/gap', {
    headers: userHeaders(USER),
  })
  const gapBody = (await gapResponse.json()) as {
    data: { to_improve: unknown[] }
  }
  const count = Math.min(3, gapBody.data.to_improve.length)
  const expected =
    count === 0
      ? '能力差距'
      : count >= 3
        ? '能力差距 Top 3'
        : `能力差距（${count} 项）`
  await expect(
    page.locator('.dash-card').filter({ hasText: '能力差距' }).locator('h3'),
  ).toHaveText(expected)
})

test('dashboard never shows 0% or missing target while loading', async ({
  page,
}) => {
  await page.route('**/api/profile', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1200))
    await route.continue()
  })
  await page.goto('/dashboard')
  await expect(page.getByRole('heading', { level: 2, name: /Dashboard/ })).toBeVisible()
  await expect(page.locator('.page-lede .skeleton')).toBeVisible()
  await expect(page.locator('.dash-metric-ring')).toHaveCount(0)
  await expect(page.locator('body')).not.toContainText('目标岗位待设置')
  await expect(page.locator('.dash-metric-link')).toContainText('%', {
    timeout: 10_000,
  })
  await expect(page.locator('body')).toContainText('目标 数据分析师')
})

test('chat keeps the message list as the only scroll region', async ({ page }) => {
  await page.goto('/chat')
  await expect(
    page.getByRole('heading', { level: 2, name: /AI Career Advisor/ }),
  ).toBeVisible()

  const input = page.getByLabel('消息输入框')
  for (let index = 0; index < 4; index += 1) {
    await input.fill(
      `第 ${index + 1} 轮：` +
        '我想系统了解数据分析师的能力要求、学习路径和实践项目。'.repeat(8),
    )
    await page.getByRole('button', { name: '发送', exact: true }).click()
    await expect(page.locator('.message-assistant')).toHaveCount(index + 1, {
      timeout: 30_000,
    })
  }

  const metrics = await page.locator('.messages').evaluate((element) => ({
    overflow: getComputedStyle(element).overflowY,
    scrollTop: element.scrollTop,
    scrollHeight: element.scrollHeight,
    clientHeight: element.clientHeight,
  }))
  expect(['auto', 'scroll']).toContain(metrics.overflow)
  expect(metrics.scrollHeight).toBeGreaterThan(metrics.clientHeight)
  expect(metrics.scrollTop).toBeGreaterThan(0)

  const appOverflow = await page
    .locator('.app-main')
    .evaluate((element) => getComputedStyle(element).overflowY)
  expect(appOverflow).toBe('hidden')
  expect(await page.evaluate(() => window.scrollY)).toBe(0)

  const composer = await page.locator('.composer').boundingBox()
  const viewport = page.viewportSize()
  expect(composer).not.toBeNull()
  expect(viewport).not.toBeNull()
  expect(composer!.y + composer!.height).toBeLessThanOrEqual(
    viewport!.height + 1,
  )
})

test('mobile layouts avoid horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  for (const path of ['/dashboard', '/profile', '/market', '/roadmap', '/chat']) {
    await page.goto(path)
    await page.waitForTimeout(500)
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    )
    expect(overflow).toBeLessThanOrEqual(1)
    await expect(page.locator('.app-main')).toBeVisible()
    if (path === '/chat') {
      const emptyOverflow = await page
        .locator('.chat-empty')
        .evaluate((element) => element.scrollHeight - element.clientHeight)
      expect(emptyOverflow).toBeLessThanOrEqual(1)
    }
  }
})