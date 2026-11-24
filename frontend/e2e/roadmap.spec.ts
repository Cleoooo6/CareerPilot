import { expect, fileUser, test, userHeaders } from './fixtures'

const USER = fileUser('roadmap')
test.use({ extraHTTPHeaders: { 'X-User-Id': USER } })

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
    headers: userHeaders(USER),
  })
  expect(profile.ok()).toBeTruthy()
})

test('roadmap gap table, stage expansion, task actions and history drawer', async ({
  page,
}) => {
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  page.on('dialog', (dialog) => dialog.accept())

  await page.goto('/roadmap')
  await expect(page.getByRole('heading', { level: 2, name: /My Roadmap/ })).toBeVisible()

  const gapCard = page.getByTestId('roadmap-gap')
  await expect(gapCard).toContainText('技能差距')
  await expect(gapCard).toContainText('演示数据')
  await expect(gapCard).toContainText('尚无记录')
  await expect(gapCard).toContainText('资料已确认不等于客观验证')
  await expect(gapCard).toContainText('展开全部')
  await gapCard.getByRole('button', { name: /展开全部/ }).click()
  await expect(gapCard).toContainText('有记录')
  await expect(gapCard).toContainText('Python')
  await expect(gapCard).toContainText('SQL')

  await page.getByRole('button', { name: /生成新版本|重新生成草稿/ }).click()
  const draftCard = page.getByTestId('roadmap-draft')
  await expect(draftCard).toContainText('确认并启用')
  await expect(draftCard).toContainText('验收：')
  await draftCard.getByRole('button', { name: '确认并启用' }).click()
  await expect(page.getByText(/成长路线已启用/)).toBeVisible()

  const currentCard = page.getByTestId('roadmap-current')
  await expect(currentCard).toContainText('当前正式路线')
  await expect(currentCard).toContainText('验收标准')

  const firstTask = currentCard.locator('.task-v2').first()
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

  await page.getByRole('button', { name: /重新生成草稿|生成新版本/ }).click()
  await page
    .getByTestId('roadmap-draft')
    .getByRole('button', { name: '确认并启用' })
    .click()
  await expect(page.getByText(/成长路线已启用/)).toBeVisible()

  await page.getByTestId('roadmap-history').click()
  const drawer = page.locator('.drawer')
  await expect(drawer).toBeVisible()
  await expect(drawer).toContainText('历史版本')
  await expect(drawer).toContainText('正式路线')
  await drawer
    .locator('.version-row')
    .last()
    .getByRole('button', { name: '查看' })
    .click()
  await expect(drawer).toContainText('个任务')

  await expect(page.locator('body')).not.toContainText('Mock')
  expect(pageErrors).toEqual([])
})