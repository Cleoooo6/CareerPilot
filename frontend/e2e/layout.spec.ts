import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { expect, test, type Page } from '@playwright/test'

type MarketFixture = {
  source: {
    name: string
    source_type: string
    dataset_kind: string
    license_note: string
    base_url: string | null
  }
  jobs: Array<Record<string, unknown>>
}

const fixture: MarketFixture = JSON.parse(
  readFileSync(
    join(process.cwd(), 'e2e', 'fixtures', 'market-synthetic-jobs.json'),
    'utf-8',
  ),
)

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
  const profile = await request.put('/api/profile', {
    data: { data: PROFILE },
  })
  expect(profile.ok()).toBeTruthy()

  const imported = await request.post('/api/market/import', { data: fixture })
  expect(imported.ok()).toBeTruthy()

  const current = await request.get('/api/roadmap/current')
  expect(current.ok()).toBeTruthy()
  const currentBody = (await current.json()) as {
    data: { roadmap: { id: string } | null }
  }
  if (currentBody.data.roadmap) return

  const generated = await request.post('/api/roadmap/generate', {
    data: {},
  })
  expect(generated.ok()).toBeTruthy()
  const generatedBody = (await generated.json()) as {
    data: { id: string }
  }
  const confirmed = await request.post(
    `/api/roadmap/${generatedBody.data.id}/confirm`,
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
  await expect(page.getByRole('heading', { name: '职业概览' })).toBeVisible()
  await assertNaturalScroll(page)
})

test('market page scrolls naturally from the page body', async ({ page }) => {
  await page.goto('/market')
  await expect(page.locator('.market-meta')).toBeVisible()
  await assertNaturalScroll(page)
})

test('roadmap page scrolls naturally from the page body', async ({ page }) => {
  await page.goto('/roadmap')
  await expect(page.getByTestId('roadmap-current')).toBeVisible()
  await assertNaturalScroll(page)
})

test('chat keeps the message list as the only scroll region', async ({ page }) => {
  await page.goto('/chat')
  await expect(
    page.getByRole('heading', { name: '探索职业方向，找到下一步' }),
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
  for (const path of ['/profile', '/market', '/roadmap', '/chat']) {
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