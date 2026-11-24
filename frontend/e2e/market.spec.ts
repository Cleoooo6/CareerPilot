import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { expect, fileUser, test } from './fixtures'

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

const USER = fileUser('market')
test.use({ extraHTTPHeaders: { 'X-User-Id': USER } })

const SOURCE_NAME = fixture.source.name.replace(/合成/g, '演示')

test('market trends render honest metadata and real distributions', async ({
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
  await expect(page.getByRole('heading', { level: 2, name: /Market Radar/ })).toBeVisible()

  const metaBar = page.locator('.market-meta')
  await expect(metaBar).toContainText('演示数据')
  await expect(metaBar).toContainText(`样本 ${fixture.jobs.length} 条`)
  await expect(metaBar).toContainText('样本达标')

  const jobNumber = page.locator('.market-number').filter({ hasText: '岗位样本' })
  await expect(jobNumber).toContainText(String(fixture.jobs.length))

  const skillApi = await request.get('/api/market/skills?limit=20')
  const skillBody = (await skillApi.json()) as {
    data: { items: Array<{ skill: string }> }
  }
  const totalSkills = skillBody.data.items.length
  const skillPanel = page.locator('section.market-panel').filter({ hasText: '高频技能' })
  await expect(skillPanel.locator('.market-bar-label').first()).toContainText('Python')
  await expect(skillPanel).toContainText(`共 ${totalSkills} 项`)
  await expect(skillPanel.locator('.market-bar-row')).toHaveCount(8)
  await skillPanel
    .getByRole('button', { name: `展开全部 ${totalSkills} 项` })
    .click()
  await expect(skillPanel.locator('.market-bar-row')).toHaveCount(totalSkills)

  const rolePanel = page
    .locator('section.market-panel')
    .filter({ hasText: '职业方向需求' })
  await expect(rolePanel).toContainText('数据分析师')
  await expect(rolePanel).toContainText('算法工程师')

  await page.locator('.market-source-panel summary').click()
  const sourcePanel = page.locator('.market-source-panel')
  await expect(sourcePanel).toContainText(SOURCE_NAME)
  await expect(sourcePanel).toContainText('演示数据')

  const trendPanel = page
    .locator('section.market-panel')
    .filter({ hasText: '技能需求趋势' })
  await expect(trendPanel.locator('.trend-point')).toHaveCount(4)
  await expect(trendPanel).toContainText('2026-08')

  await expect(page.locator('.market-warning')).toContainText(
    '演示数据，仅用于体验，不代表真实招聘市场',
  )

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
    page.locator('.market-number').filter({ hasText: '岗位样本' }),
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

test('industry pulse renders example content with filters and four states', async ({
  page,
}) => {
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))

  await page.goto('/market?view=pulse')
  await expect(page.getByRole('heading', { level: 2, name: /Market Radar/ })).toBeVisible()
  await expect(page.locator('.pulse-example-note')).toContainText('示例')

  await expect(page.locator('.pulse-card')).toHaveCount(8)
  await expect(page.locator('.pulse-card').first()).toContainText('示例：')
  await expect(page.locator('.pulse-card').first()).toContainText('AI 解读')
  await expect(page.locator('.pulse-card').first()).toContainText('职业影响')

  await page.getByRole('button', { name: '金融', exact: true }).click()
  await expect(page.locator('.pulse-card')).toHaveCount(2)
  for (const card of await page.locator('.pulse-card').all()) {
    await expect(card).toContainText('金融')
  }

  await page.getByRole('button', { name: '空', exact: true }).click()
  await expect(page.getByRole('heading', { name: '空状态预览' })).toBeVisible()
  await page.getByRole('button', { name: '查看全部行业' }).click()
  await expect(page.locator('.pulse-card')).toHaveCount(8)

  await page.getByRole('button', { name: '错误', exact: true }).click()
  await expect(page.getByText(/行业动态没加载出来/)).toBeVisible()
  await page.getByRole('button', { name: '重新加载' }).click()
  await expect(page.locator('.pulse-card')).toHaveCount(8)

  await page.getByRole('button', { name: '加载', exact: true }).click()
  await expect(page.locator('.skeleton-block')).toHaveCount(2)
  await page.getByRole('button', { name: '正常', exact: true }).click()
  await expect(page.locator('.pulse-card')).toHaveCount(8)

  await expect(page.locator('body')).not.toContainText('Mock')
  expect(pageErrors).toEqual([])
})