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

const PROFILE = {
  basic: {
    name: '路线测试用户',
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
      id: 'e2e-python',
      name: 'Python',
      proficiency: '熟练',
      evidence: '课程项目',
      category: '编程语言',
    },
    {
      id: 'e2e-sql',
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
  const profile = await request.put('/api/profile', {
    data: { data: PROFILE },
  })
  expect(profile.ok()).toBeTruthy()
  const imported = await request.post('/api/market/import', { data: fixture })
  expect(imported.ok()).toBeTruthy()
})

test('roadmap generation, confirmation, task tracking, and history', async ({
  page,
}) => {
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))

  await page.goto('/roadmap')
  await expect(
    page.getByRole('heading', { name: '从当前状态，走向目标' }),
  ).toBeVisible()

  const gapCard = page.getByTestId('roadmap-gap')
  await expect(gapCard).toContainText('技能差距')
  await expect(gapCard).toContainText('演示数据')
  await expect(gapCard).toContainText('尚无记录（不等于不会）')
  await expect(gapCard).toContainText('有记录且有证据')
  await expect(gapCard).toContainText('资料已确认')
  await expect(gapCard).toContainText('没有记录不等于不具备')
  await expect(gapCard).toContainText('Python')
  await expect(gapCard).toContainText('SQL')

  await page.locator('.roadmap-head-actions button.primary').click()
  const draftCard = page.getByTestId('roadmap-draft')
  await expect(draftCard).toContainText('确认并启用')
  await expect(draftCard).toContainText('验收：')
  await draftCard.getByRole('button', { name: '确认并启用' }).click()
  await expect(page.getByText('成长路线已启用', { exact: true })).toBeVisible()

  const currentCard = page.getByTestId('roadmap-current')
  await expect(currentCard).toContainText('当前正式路线')
  await expect(currentCard).toContainText('正式')
  await expect(currentCard).toContainText('验收标准：')

  const firstTask = currentCard.locator('.roadmap-task').first()
  await expect(firstTask).toContainText('待开始')
  await firstTask.getByRole('button', { name: '开始任务' }).click()
  await expect(firstTask).toContainText('进行中')

  await firstTask
    .locator('textarea')
    .fill('完成 SQL 分析项目，仓库链接：https://example.invalid/roadmap')
  await firstTask.getByRole('button', { name: '标记完成' }).click()
  await expect(firstTask).toContainText('已完成')
  await expect(firstTask).toContainText('已记录成果：完成 SQL 分析项目')

  await page.reload()
  const reloadedCurrent = page.getByTestId('roadmap-current')
  await expect(reloadedCurrent).toContainText('已完成')
  await expect(reloadedCurrent).toContainText(
    'https://example.invalid/roadmap',
  )

  await page.locator('.roadmap-head-actions button.primary').click()
  await page
    .getByTestId('roadmap-draft')
    .getByRole('button', { name: '确认并启用' })
    .click()

  const historyPanel = page.getByTestId('roadmap-history')
  await expect(historyPanel).toContainText('正式路线')
  await expect(historyPanel).toContainText('历史版本')
  await historyPanel
    .locator('.revision-list li')
    .last()
    .getByRole('button', { name: '查看' })
    .click()
  await expect(historyPanel).toContainText('个任务')
  await expect(page.locator('body')).not.toContainText('Mock')

  expect(pageErrors).toEqual([])
})