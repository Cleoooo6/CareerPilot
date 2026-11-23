import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { expect, test } from '@playwright/test'

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

const SOURCE_NAME = fixture.source.name.replace(/合成/g, '演示')

test.beforeAll(async ({ request }) => {
  const response = await request.post('/api/market/import', { data: fixture })
  expect(response.ok()).toBeTruthy()
  const body = (await response.json()) as {
    data: { total: number; imported: number; duplicates: number; failed: number }
  }
  expect(body.data.total).toBe(fixture.jobs.length)
  expect(body.data.failed).toBe(0)
  expect(body.data.imported + body.data.duplicates).toBe(fixture.jobs.length)
})

test('market radar renders demo dataset with honest metadata', async ({
  page,
  request,
}) => {
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))

  const apiResponse = await request.get('/api/market/overview')
  expect(apiResponse.ok()).toBeTruthy()
  const apiBody = (await apiResponse.json()) as {
    data: { total_jobs: number; meta: { dataset_kinds: string[]; warnings: string[] } }
  }
  expect(apiBody.data.total_jobs).toBe(fixture.jobs.length)
  expect(apiBody.data.meta.dataset_kinds).toContain('synthetic')

  await page.goto('/market')
  await expect(
    page.getByRole('heading', { name: '看清市场需要什么' }),
  ).toBeVisible()

  const metaBar = page.locator('.market-meta')
  await expect(metaBar).toContainText('演示数据')
  await expect(metaBar).toContainText(`样本 ${fixture.jobs.length} 条`)
  await expect(metaBar).toContainText('样本达标')
  await expect(page.locator('.market-warning')).toContainText(
    '演示数据，仅用于体验，不代表真实招聘市场',
  )

  const skillPanel = page.locator('section.market-panel').filter({ hasText: '高频技能' })
  await expect(skillPanel.locator('.market-bar-label').first()).toContainText('Python')

  const rolePanel = page
    .locator('section.market-panel')
    .filter({ hasText: '职业方向需求' })
  await expect(rolePanel).toContainText('数据分析师')
  await expect(rolePanel).toContainText('算法工程师')

  const sourcePanel = page
    .locator('section.market-panel')
    .filter({ hasText: '数据来源与授权说明' })
  await expect(sourcePanel).toContainText(SOURCE_NAME)
  await expect(sourcePanel).toContainText('演示数据')
  await expect(sourcePanel).toContainText(
    '演示数据，仅用于体验，不代表真实招聘市场',
  )

  const trendPanel = page
    .locator('section.market-panel')
    .filter({ hasText: '技能需求趋势' })
  await expect(trendPanel.locator('.trend-point')).toHaveCount(4)
  await expect(trendPanel).toContainText('2026-08')

  expect(pageErrors).toEqual([])
})

test('role filter narrows every market panel through the real API', async ({ page }) => {
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))

  await page.goto('/market')
  await expect(page.locator('.market-meta')).toContainText(
    `样本 ${fixture.jobs.length} 条`,
  )

  await page.getByLabel('职业方向').selectOption('算法工程师')

  const metaBar = page.locator('.market-meta')
  await expect(metaBar).toContainText('样本 6 条')
  await expect(metaBar).toContainText('演示数据')
  await expect(
    page.locator('.market-card').filter({ hasText: '岗位样本' }),
  ).toContainText('6')

  const educationPanel = page
    .locator('section.market-panel')
    .filter({ hasText: '学历要求' })
  await expect(educationPanel).toContainText('硕士')

  const skillPanel = page.locator('section.market-panel').filter({ hasText: '高频技能' })
  await expect(skillPanel).toContainText('PyTorch')

  await expect(
    page.locator('section.market-panel').filter({ hasText: '职业方向需求' }),
  ).toContainText('算法工程师')

  expect(pageErrors).toEqual([])
})