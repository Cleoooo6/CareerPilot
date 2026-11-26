import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { createSession, expect, useUser } from './fixtures'

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

const test = useUser('market')

const SOURCE_NAME = fixture.source.name.replace(/合成/g, '演示')

test('market trends render honest metadata and real distributions', async ({
  page,
  session,
}) => {
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))

  const apiResponse = await session.api.get('/api/market/overview')
  expect(apiResponse.ok()).toBeTruthy()
  const apiBody = (await apiResponse.json()) as {
    data: { total_jobs: number; meta: { dataset_kinds: string[]; warnings: string[] } }
  }
  expect(apiBody.data.total_jobs).toBe(fixture.jobs.length)
  expect(apiBody.data.meta.dataset_kinds).toContain('synthetic')

  await page.goto('/market')
  await expect(page.getByRole('heading', { level: 1, name: /Market Radar/ })).toBeVisible()

  const metaBar = page.locator('.market-meta')
  await expect(metaBar).toContainText('演示数据')
  await expect(metaBar).toContainText(`样本 ${fixture.jobs.length} 条`)
  await expect(metaBar).toContainText('样本达标')

  const jobNumber = page.locator('.market-number').filter({ hasText: '岗位样本' })
  await expect(jobNumber).toContainText(String(fixture.jobs.length))

  const skillApi = await session.api.get('/api/market/skills?limit=20')
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

  await expect(page.locator('.market-warning')).not.toContainText(
    '演示数据，仅用于体验，不代表真实招聘市场',
  )
  await expect(sourcePanel).toContainText(
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

test('industry pulse reads real API data, filters and can refresh', async ({
  page,
}) => {
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))

  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('/market?view=pulse')
  await expect(page.getByRole('heading', { level: 1, name: /Market Radar/ })).toBeVisible()
  await expect(page.locator('.pulse-card')).toHaveCount(16)
  await expect(page.locator('.pulse-source-note')).toContainText('RSS')
  await expect(page.locator('.pulse-source-note')).toContainText('Asia/Shanghai')
  await expect(page.locator('.pulse-source-note')).toContainText(
    '部分来源仅提供元数据',
  )
  await expect(page.getByText('行业筛选', { exact: true })).toBeVisible()
  await expect(page.getByText('地区筛选', { exact: true })).toBeVisible()
  const industryLabelBox = await page
    .getByText('行业筛选', { exact: true })
    .boundingBox()
  const regionLabelBox = await page
    .getByText('地区筛选', { exact: true })
    .boundingBox()
  expect(Math.abs((industryLabelBox?.y ?? 0) - (regionLabelBox?.y ?? 0))).toBeLessThan(4)
  await expect(page.locator('.pulse-card').filter({ hasText: 'TechCrunch' })).toHaveCount(6)
  await expect(page.locator('.pulse-card').first()).toContainText('AI 未启用')
  await expect(page.locator('body')).not.toContainText('示例内容')
  await expect(page.locator('body')).not.toContainText('示例：')
  await expect(page.locator('body')).not.toContainText('出生人口')
  await expect(page.locator('body')).not.toContainText('盘王节')

  const firstCard = page.locator('.pulse-card').first()
  const aiFold = firstCard.locator('.pulse-ai-fold')
  await expect(aiFold).toHaveCount(0)
  await expect(firstCard).toContainText('AI 未启用')
  await expect(firstCard).not.toContainText('该来源仅提供元数据')
  const sourceName = (
    await firstCard.locator('.pulse-source-pill').innerText()
  ).trim()
  await expect(firstCard.getByText(sourceName, { exact: true })).toHaveCount(1)
  await expect(firstCard.locator('.pulse-row-side')).not.toContainText(sourceName)
  const cardBox = await firstCard.boundingBox()
  expect(cardBox?.height ?? 999).toBeLessThan(280)
  await expect(
    firstCard.getByRole('link', { name: /查看原文/ }),
  ).toHaveAttribute('title', /新标签页/)

  const rowLayout = await page
    .locator('.pulse-row')
    .first()
    .evaluate((el) => {
      const style = getComputedStyle(el)
      return {
        display: style.display,
        columns: style.gridTemplateColumns.split(' ').length,
      }
    })
  expect(rowLayout.display).toBe('grid')
  expect(rowLayout.columns).toBeGreaterThanOrEqual(2)

  const refreshButton = page.getByRole('button', { name: '手动更新' })
  const refreshBox = await refreshButton.boundingBox()
  expect(refreshBox?.width ?? 0).toBeGreaterThanOrEqual(96)
  expect(refreshBox?.height ?? 99).toBeLessThan(60)

  const help = page.getByRole('button', { name: '查看数字科技与通信说明' })
  const panel = page.locator('.pulse-help-panel')
  await help.hover()
  await expect(panel).toBeVisible()
  await expect(panel).toContainText('计算机科学与技术')
  await expect(panel).toContainText('并非限定范围')
  const panelBox = await panel.boundingBox()
  const regionButtonBox = await page
    .getByRole('button', { name: '国际', exact: true })
    .boundingBox()
  expect(panelBox?.y ?? 0).toBeGreaterThan(
    (regionButtonBox?.y ?? 0) + (regionButtonBox?.height ?? 0),
  )
  await help.focus()
  await expect(panel).toBeVisible()
  await help.click()
  await expect(page.getByRole('button', { name: '全部行业', exact: true })).toHaveClass(
    /is-active/,
  )
  await help.hover()
  await page.getByRole('button', { name: '关闭行业说明' }).click()
  await expect(panel).toBeHidden()
  await help.hover()
  await page.keyboard.press('Escape')
  await expect(panel).toBeHidden()

  await page.getByRole('button', { name: '金融与保险', exact: true }).click()
  await expect(panel).toBeHidden()
  await expect(page.locator('.pulse-card')).toHaveCount(1)
  for (const card of await page.locator('.pulse-card').all()) {
    await expect(card).toContainText('金融与保险')
  }

  await page.getByRole('button', { name: '全部行业', exact: true }).click()
  await page.getByRole('button', { name: '国际', exact: true }).click()
  await expect(page.locator('.pulse-card')).toHaveCount(4)
  await page.getByRole('button', { name: '中国', exact: true }).click()
  await expect(page.locator('.pulse-card')).toHaveCount(12)
  await page.getByRole('button', { name: '全部地区', exact: true }).click()
  await expect(page.locator('.pulse-card')).toHaveCount(16)

  await page.getByRole('button', { name: '制造业与工业科技', exact: true }).click()
  await expect(page.locator('.market-warning')).toContainText('暂无已启用的可靠来源')
  await page.getByRole('button', { name: '全部行业', exact: true }).click()

  await page.route('**/api/industry-pulse/refresh', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: true,
        data: {
          run: {
            id: '00000000-0000-0000-0000-000000000001',
            status: 'succeeded',
            started_at: '2026-11-24T12:00:00Z',
            finished_at: '2026-11-24T12:00:01Z',
            sources_total: 4,
            sources_ok: 4,
            sources_failed: 0,
            articles_fetched: 8,
            articles_inserted: 0,
            articles_duplicates: 8,
            error_message: '',
            details: [],
          },
        },
        request_id: 'e2e',
      }),
    })
  })
  await page.getByRole('button', { name: '手动更新' }).first().click()
  await expect(page.locator('.pulse-run')).toContainText('最近更新')
  await expect(page.locator('.pulse-run')).toContainText('来源成功')
  await expect(page.locator('.pulse-run')).toContainText('最近一次采集')
  await expect(page.locator('.pulse-run')).toContainText('去重后入库')

  await expect(page.locator('body')).not.toContainText('Mock')
  expect(pageErrors).toEqual([])
})

test('industry pulse shows a labeled loading skeleton', async ({ page }) => {
  await page.route('**/api/industry-pulse?*', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 600))
    await route.continue()
  })
  await page.goto('/market?view=pulse')
  await expect(page.locator('.pulse-loading-note')).toContainText(
    '正在加载动态',
  )
  await expect(page.locator('.pulse-skeleton')).toHaveCount(3)
  await expect(page.locator('.pulse-card').first()).toBeVisible()
})

test('industry pulse clears stale counts while switching views', async ({
  page,
  session,
}) => {
  await session.api.put('/api/profile', {
    data: {
      basic: { location: '上海', education_level: '本科' },
      goals: { target_role: '数据分析师', target_industry: '互联网' },
      skills: [
        { name: 'Python', evidence: '课程项目', verification: 'confirmed' },
        { name: 'SQL', evidence: '', verification: 'confirmed' },
      ],
    },
  })
  await page.goto('/market?view=pulse')
  await expect(page.locator('.pulse-count')).toContainText('共 16 条')
  await page.route('**/api/industry-pulse/personal?*', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 500))
    await route.continue()
  })
  const personalResponse = page.waitForResponse(
    (response) =>
      response.url().includes('/api/industry-pulse/personal') &&
      response.status() === 200,
  )
  await page.getByRole('tab', { name: '与你相关' }).click()
  await expect(page.locator('.pulse-count')).toBeHidden()
  await expect(page.locator('.pulse-personal-banner')).toBeHidden()
  await personalResponse
  await expect(page.locator('.pulse-personal-banner')).toBeVisible()
  await expect(page.locator('.pulse-count')).toBeVisible()
  await expect(page.locator('.pulse-count')).not.toContainText('共 16 条')
})

test('industry pulse shows an error state and retries', async ({ page }) => {
  await page.route('**/api/industry-pulse?*', async (route) => {
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({
        ok: false,
        error: { code: 'TEST_PULSE_ERROR', message: '行业动态暂时无法读取' },
        request_id: 'e2e',
      }),
    })
  })
  await page.goto('/market?view=pulse')
  await expect(page.getByRole('button', { name: '重新加载' })).toBeVisible()
  await page.unroute('**/api/industry-pulse?*')
  await page.getByRole('button', { name: '重新加载' }).click()
  await expect(page.locator('.pulse-card')).toHaveCount(16)
})

test('industry pulse shows an empty state and can reload', async ({ page, session }) => {
  const response = await session.api.get('/api/industry-pulse')
  const body = (await response.json()) as {
    data: Record<string, unknown>
  }
  const empty = { ...body.data, items: [], total: 0 }
  await page.route('**/api/industry-pulse?*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, data: empty, request_id: 'e2e' }),
    })
  })
  await page.goto('/market?view=pulse')
  await expect(page.getByRole('heading', { name: '暂时没有行业动态' })).toBeVisible()
  await page.unroute('**/api/industry-pulse?*')
  await page.getByRole('button', { name: '重新加载' }).click()
  await expect(page.locator('.pulse-card')).toHaveCount(16)
})

test('industry pulse shows honest empty state for industry without relevant news', async ({
  page,
}) => {
  await page.route('**/api/industry-pulse?*', async (route) => {
    const response = await route.fetch()
    const payload = await response.json()
    payload.data.items = []
    payload.data.total = 0
    payload.data.industries = payload.data.industries.map(
      (item: { id: string; article_count: number }) =>
        item.id === 'sports_industry' ? { ...item, article_count: 0 } : item,
    )
    await route.fulfill({ response, json: payload })
  })
  await page.goto('/market?view=pulse')
  const sports = page.getByRole('button', { name: '体育产业', exact: true })
  await expect(sports).toHaveClass(/is-unavailable/)
  await expect(
    page.locator('.pulse-chip-wrap').filter({ has: sports }).locator('.pulse-no-source'),
  ).toContainText('暂无来源')
  await sports.click()
  await expect(page.getByRole('heading', { name: '暂无高相关行业动态' })).toBeVisible()
  await expect(page.locator('.state-card')).toContainText(
    '未分类与宏观信号不会计入该行业',
  )
})

test('industry trends show overall evidence and personalized rationale', async ({
  page,
  session,
}) => {
  const profile = await session.api.put('/api/profile', {
    data: {
      basic: { location: '上海', education_level: '本科' },
      goals: { target_role: '数据分析师', target_industry: '互联网' },
      skills: [
        { name: 'Python', evidence: '课程项目', verification: 'confirmed' },
        { name: 'SQL', evidence: '', verification: 'confirmed' },
      ],
    },
  })
  expect(profile.ok()).toBeTruthy()

  await page.goto('/market?view=trends')
  const panel = page.locator('.industry-trends')
  await expect(panel.getByRole('tab', { name: '整体行业趋势' })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await expect(panel.locator('.trend-card').first()).toBeVisible()
  await expect(panel.locator('.trend-insufficient')).toContainText('证据不足的行业')
  await panel.locator('.trend-evidence summary').first().click()
  await expect(panel.locator('.trend-evidence-body').first()).toContainText('新闻证据')

  await panel.getByRole('tab', { name: '与你相关' }).click()
  await expect(panel.locator('.trend-profile-banner')).toContainText('数据分析师')
  await expect(panel.locator('.trend-card.personal').first()).toBeVisible()
  await expect(panel.getByText('为什么与你有关').first()).toBeVisible()
  await expect(panel.getByRole('link', { name: '去 My Roadmap 确认' }).first()).toBeVisible()
  await expect(
    panel.getByText('资料确认不等于客观能力验证').first(),
  ).toBeVisible()
  await expect(panel.locator('.trend-evidence').last()).toBeVisible()
})

test('industry trends show honest insufficient state for arts', async ({ page }) => {
  await page.goto('/market?view=trends')
  const panel = page.locator('.industry-trends')
  await Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().includes('/api/market/industry-trends?') &&
        response.status() === 200,
    ),
    panel.locator('.trend-filters select').first().selectOption('arts_design'),
  ])
  await expect(panel.getByRole('heading', { name: '证据不足，暂无法形成可靠趋势' })).toBeVisible()
  await expect(panel.locator('.trend-insufficient')).toContainText('艺术与设计产业')
})

test('personal trends explain missing profile instead of inventing a match', async ({
  page,
}) => {
  await page.context().clearCookies()
  await createSession(page.context().request, 'market-trends-empty')
  await page.goto('/market?view=trends')
  const panel = page.locator('.industry-trends')
  await panel.getByRole('tab', { name: '与你相关' }).click()
  await expect(panel.getByRole('heading', { name: '职业画像资料不足' })).toBeVisible()
  await expect(panel).toContainText('不会凭空推断')
  await expect(panel.getByRole('link', { name: '完善 Profile' })).toBeVisible()
})

test('personalized industry pulse explains match and keeps filters usable', async ({
  page,
  session,
}) => {
  await session.api.put('/api/profile', {
    data: {
      basic: { location: '上海', education_level: '本科' },
      goals: { target_role: '数据分析师', target_industry: '互联网' },
      skills: [
        { name: 'Python', evidence: '课程项目', verification: 'confirmed' },
        { name: 'SQL', evidence: '', verification: 'confirmed' },
      ],
    },
  })

  await page.setViewportSize({ width: 1920, height: 1080 })
  await page.goto('/market?view=pulse')
  const personalResponse = () =>
    page.waitForResponse(
      (response) =>
        response.url().includes('/api/industry-pulse/personal') &&
        response.status() === 200,
    )
  await page.getByRole('tab', { name: '全部动态' }).waitFor({ state: 'visible' })
  await expect(page.getByRole('tab', { name: '全部动态' })).toHaveAttribute(
    'aria-selected',
    'true',
  )
  await Promise.all([
    personalResponse(),
    page.getByRole('tab', { name: '与你相关' }).click(),
  ])
  await expect(page.locator('.pulse-personal-banner')).toContainText('数据分析师')
  await expect(page.locator('.pulse-match').first()).toContainText('为什么与你相关')
  await expect(page.locator('.pulse-match').first()).toContainText('目标行业')
  await expect(page.locator('.pulse-match-types').first()).toBeVisible()
  await expect(page.locator('.pulse-match').first()).toContainText(
    '不生成综合分数',
  )
  const personalRefreshBox = await page
    .getByRole('button', { name: '手动更新' })
    .boundingBox()
  expect(personalRefreshBox?.width ?? 0).toBeGreaterThanOrEqual(96)
  expect(personalRefreshBox?.height ?? 99).toBeLessThan(60)

  await Promise.all([
    personalResponse(),
    page.getByRole('button', { name: '数字科技与通信', exact: true }).click(),
  ])
  await expect(page.locator('.pulse-card').first()).toBeVisible()

  await Promise.all([
    personalResponse(),
    page.getByRole('button', { name: '艺术与设计产业', exact: true }).click(),
  ])
  await expect(
    page.getByRole('heading', { name: '暂无与你相关的行业动态' }),
  ).toBeVisible()
})

test('personalized industry pulse prompts for a real profile', async ({ page }) => {
  await page.context().clearCookies()
  await createSession(page.context().request, 'pulse-personal-empty')
  await page.goto('/market?view=pulse')
  await page.getByRole('tab', { name: '与你相关' }).click()
  await expect(page.getByRole('heading', { name: '先完善职业画像' })).toBeVisible()
  await expect(page.getByRole('link', { name: '完善 Profile' })).toBeVisible()
})

test('industry filters stay consistent across trend and market statistics', async ({
  page,
}) => {
  await page.goto('/market?view=trends')
  const panel = page.locator('.industry-trends')
  await Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().includes('/api/market/overview') &&
        response.url().includes('industry=digital_tech_comms') &&
        response.status() === 200,
    ),
    page.waitForResponse(
      (response) =>
        response.url().includes('/api/market/industry-trends') &&
        response.url().includes('industry=digital_tech_comms') &&
        response.status() === 200,
    ),
    panel.locator('.trend-filters select').first().selectOption(
      'digital_tech_comms',
    ),
  ])
  await expect(page.locator('.market-scope-note')).toContainText('数字科技与通信')
  await expect(page.locator('.market-meta')).toContainText('样本 11 条')
  await expect(
    page.locator('.market-number').filter({ hasText: '岗位样本' }),
  ).toContainText('11')
  await expect(panel.locator('.trend-filter-note')).toContainText(
    '已按所选行业过滤',
  )
  await expect(panel.locator('.trend-insufficient')).toBeVisible()
  await expect(panel.locator('.trend-insufficient')).toContainText(
    '所选行业证据充足，暂无证据不足项',
  )
  await expect(
    page.locator('.market-note').filter({ hasText: '最大余数法' }),
  ).toContainText('最大余数法')

  const distributionCards = page.locator('.market-panel-grid.three .market-panel')
  for (const card of await distributionCards.all()) {
    const values = await card.locator('.market-bar-value').allInnerTexts()
    const sum = values.reduce((total, value) => total + Number.parseInt(value, 10), 0)
    expect(sum).toBe(100)
  }

  await Promise.all([
    page.waitForResponse(
      (response) =>
        response.url().includes('/api/market/overview') &&
        response.url().includes('months=6') &&
        response.status() === 200,
    ),
    panel.locator('.trend-filters select').nth(1).selectOption('6'),
  ])
  await expect(page.locator('.market-warning')).toContainText(
    '岗位数据仅覆盖约 4 个月',
  )
  await expect(page.locator('.market-warning')).not.toContainText(
    '演示数据，仅用于体验，不代表真实招聘市场',
  )

  await page.getByRole('button', { name: '刷新数据', exact: true }).click()
  await expect(page.getByText(/已刷新/).first()).toBeVisible()
})
