import { expect, test } from '@playwright/test'
import { fileURLToPath } from 'node:url'

const resumeFixture = fileURLToPath(
  new URL('./fixtures/fictional-resume.docx', import.meta.url),
)

test('career portrait leads and source management still works', async ({
  page,
}) => {
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))
  page.on('dialog', (dialog) => dialog.accept())

  await page.goto('/profile')
  await expect(
    page.getByRole('heading', { name: '你的职业画像' }),
  ).toBeVisible()
  await page.waitForLoadState('networkidle')

  const deleteButton = page.getByRole('button', { name: '删除画像' })
  if (await deleteButton.count()) {
    await deleteButton.click()
    await expect(page.getByText('职业画像已删除')).toBeVisible()
  }

  await expect(page.getByRole('heading', { name: '资料管理' })).toBeVisible()

  await page.getByLabel('姓名').fill('林小舟')
  await page.getByLabel('目标岗位').fill('数据分析师')
  await page.getByLabel('所在地').fill('上海')

  await page.getByRole('button', { name: '添加技能' }).click()
  await page.getByLabel('技能名称').fill('Python')
  await page.getByLabel('熟练程度').fill('熟练')
  await page.getByLabel('相关证据').fill('课程项目')
  await page.getByLabel('技能分类').fill('编程语言')

  await page.getByRole('button', { name: '保存画像' }).click()
  await expect(page.getByText('职业画像已保存，并记录了新版本')).toBeVisible()

  await expect(page.getByRole('heading', { name: '职业概览' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '能力结构' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '职业方向' })).toBeVisible()

  const skillCard = page.locator('.skill-card').first()
  await expect(skillCard).toContainText('Python')
  await expect(skillCard).toContainText('熟练')
  await expect(skillCard).toContainText('手动录入')
  await expect(skillCard).toContainText('已确认')
  await expect(skillCard).toContainText('课程项目')
  await expect(page.locator('.revision-list')).toContainText(/v\d+/)
  await expect(page.locator('.revision-list')).toContainText('手动保存')

  const market = page.getByTestId('profile-market-match')
  await expect(market).toBeVisible()
  await expect(market.getByText(/演示数据|真实数据|无数据/).first()).toBeVisible()
  await expect(market).toContainText('未记录不等于不具备')
  await expect(market).toContainText('不做能力评分')

  await page.reload()
  await expect(page.getByLabel('姓名')).toHaveValue('林小舟')
  await expect(page.getByLabel('目标岗位')).toHaveValue('数据分析师')
  await expect(page.locator('.skill-card').first()).toContainText('Python')

  await page.getByRole('tab', { name: '简历解析' }).click()
  await page.getByLabel('简历文件').setInputFiles(resumeFixture)
  await page.getByRole('button', { name: '上传并解析' }).click()
  await expect(page.getByText('演示解析', { exact: true })).toBeVisible({
    timeout: 20_000,
  })
  await expect(page.getByText('简历已解析，请审核后确认导入')).toBeVisible()
  await page.getByRole('button', { name: '确认导入所选区块' }).click()
  await expect(page.getByText('已确认并写入职业画像')).toBeVisible()
  await expect(page.getByLabel('目标岗位')).toHaveValue('数据分析师')

  await page.getByRole('tab', { name: 'AI 分析' }).click()
  await page.getByRole('button', { name: '重新分析' }).click()
  await expect(
    page.locator('.analysis-detail').getByText('演示分析', { exact: true }),
  ).toBeVisible({ timeout: 20_000 })
  await expect(page.getByText('AI 职业分析已完成并保存')).toBeVisible()
  await expect(page.getByRole('heading', { name: '已有优势' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '未知信息' })).toBeVisible()

  await page.reload()
  await page.getByRole('tab', { name: 'AI 分析' }).click()
  await expect(page.getByRole('heading', { name: '历史分析' })).toBeVisible()
  await expect(
    page.locator('.analysis-detail').getByText('演示分析', { exact: true }),
  ).toBeVisible()
  await expect(page.locator('body')).not.toContainText('Mock')
  expect(pageErrors).toEqual([])
})