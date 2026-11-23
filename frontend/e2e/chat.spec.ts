import { expect, test } from '@playwright/test'

test('stage-one chat completes through real API and SSE', async ({ page }) => {
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))

  await page.goto('/chat')
  await expect(
    page.getByRole('heading', { name: '把职业问题说清楚，再一起拆解。' }),
  ).toBeVisible()
  await expect(page.getByText('Mock 安全模式', { exact: false }).first()).toBeVisible()

  const input = page.getByLabel('消息输入框')
  await input.fill('你好')
  const sendButton = page.getByRole('button', { name: '发送', exact: true })
  await expect(sendButton).toBeEnabled()
  await sendButton.click()

  await expect(page.locator('.message-user').last()).toContainText('你好')
  await expect(page.locator('.message-assistant').last()).toContainText(
    'CareerPilot',
    { timeout: 20_000 },
  )
  await expect(page.locator('.timeline-item[data-status="completed"]')).toHaveCount(
    2,
    { timeout: 20_000 },
  )
  expect(pageErrors).toEqual([])
})

test('unimplemented profile request is stated honestly', async ({ page }) => {
  await page.goto('/chat')
  await page.getByLabel('消息输入框').fill('帮我看看技能画像')
  const sendButton = page.getByRole('button', { name: '发送', exact: true })
  await expect(sendButton).toBeEnabled()
  await sendButton.click()
  await expect(page.locator('.message-assistant').last()).toContainText(
    '阶段三',
    { timeout: 20_000 },
  )
  await expect(page.locator('.message-assistant').last()).not.toContainText(
    '您的技能画像为',
  )
})