import { fileURLToPath } from 'node:url'

import { expect, useUser } from './fixtures'

const resumeFixture = fileURLToPath(
  new URL('./fixtures/fictional-resume.docx', import.meta.url),
)

const SEED_PROFILE = {
  basic: {
    name: 'E2E 画像测试用户',
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
  skills: [],
  education: [],
  projects: [],
  experiences: [],
}

const test = useUser('profile', async (session) => {
  const response = await session.api.put('/api/profile', {
    data: SEED_PROFILE,
  })
  expect(response.ok()).toBeTruthy()
})

test('profile five tabs, source labels, resume import and analysis still work', async ({
  page,
}) => {
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  page.on('dialog', (dialog) => dialog.accept())

  await page.goto('/profile')
  await expect(page.getByRole('heading', { level: 1, name: /Profile/ })).toBeVisible()
  await page.waitForLoadState('networkidle')

  await page.getByRole('tab', { name: /Manage Profile/ }).click()
  const deleteButton = page.getByRole('button', { name: '删除画像' })
  if (await deleteButton.count()) {
    await deleteButton.click()
    await expect(page.getByText(/职业画像已删除/)).toBeVisible()
  }

  await page.getByLabel('姓名').fill('林小舟')
  await page.getByText('职业目标', { exact: true }).click()
  await page.getByLabel('目标岗位').fill('数据分析师')
  await page.getByLabel('所在地').fill('上海')

  await page.getByText('技能清单', { exact: true }).click()
  await page.getByRole('button', { name: '添加技能' }).click()
  await page.getByLabel('技能名称').fill('Python')
  await page.getByLabel('熟练程度').fill('熟练')
  await page.getByLabel('相关证据').fill('课程项目')
  await page.getByLabel('技能分类').fill('编程语言')

  await page.getByRole('button', { name: '保存画像' }).click()
  await expect(page.getByText(/职业画像已保存/)).toBeVisible()

  await page.getByRole('tab', { name: /Overview/ }).click()
  await expect(page.getByRole('heading', { name: '基本信息' })).toBeVisible()
  await expect(page.getByText('最近动态')).toBeVisible()
  await expect(page.locator('.profile-growth-row').first()).toContainText(/v\d+/)

  await page.getByRole('tab', { name: /Skills & Interests/ }).click()
  await expect(page).toHaveURL(/tab=skills/)
  const skillRow = page.locator('.skill-row').first()
  await expect(skillRow).toContainText('Python')
  await expect(skillRow).toContainText('课程项目')
  await expect(skillRow).toContainText('有记录')

  await page.reload()
  await expect(
    page.getByRole('tab', { name: /Skills & Interests/ }),
  ).toHaveAttribute('aria-selected', 'true')
  await expect(page.locator('.skill-row').first()).toContainText('Python')

  await page.getByRole('tab', { name: /Market Match/ }).click()
  const market = page.getByTestId('profile-market-match')
  await expect(market).toBeVisible()
  await expect(market.getByText(/演示数据|真实数据|无数据/).first()).toBeVisible()
  await expect(market).toContainText('目标岗位需求技能已记录')

  await page.getByRole('tab', { name: /Growth Record/ }).click()
  await expect(page.getByRole('heading', { name: '成长记录' })).toBeVisible()

  await page.getByRole('tab', { name: /Manage Profile/ }).click()
  await page.getByText('简历导入', { exact: true }).click()
  await page.getByLabel('简历文件').setInputFiles(resumeFixture)
  await page.getByRole('button', { name: '上传并解析' }).click()
  await expect(page.getByText(/简历已解析/)).toBeVisible({ timeout: 20_000 })
  await page.getByRole('button', { name: '确认导入所选区块' }).click()
  await expect(page.getByText(/已确认并写入职业画像/)).toBeVisible()
  await expect(page.getByLabel('目标岗位').first()).toHaveValue('数据分析师')

  await page.getByText('AI 分析历史', { exact: true }).click()
  await page.getByRole('button', { name: '重新分析' }).click()
  await expect(page.getByText(/AI 职业分析已完成/)).toBeVisible({
    timeout: 20_000,
  })
  await expect(page.locator('.analysis-detail')).toContainText('AI 推断 · 待确认')
  await expect(page.locator('body')).not.toContainText('Mock')
  expect(pageErrors).toEqual([])
})