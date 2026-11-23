import { expect, test } from '@playwright/test'

test('chat workbench streams through real API and SSE', async ({ page }) => {
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))

  await page.goto('/chat')
  await expect(
    page.getByRole('heading', { name: '探索职业方向，找到下一步' }),
  ).toBeVisible()
  await expect(page.locator('.chat-empty')).toBeVisible()

  const input = page.getByLabel('消息输入框')
  await input.fill('你好')
  const sendButton = page.getByRole('button', { name: '发送', exact: true })
  await expect(sendButton).toBeEnabled()
  await sendButton.click()

  await expect(page.locator('.message-user').last()).toContainText('你好')
  const assistant = page.locator('.message-assistant').last()
  await expect(assistant).toHaveText(/\S+/, { timeout: 30_000 })
  await expect(page.locator('body')).not.toContainText('Mock')
  await expect(page.locator('body')).not.toContainText(/LangGraph|SSE/)
  expect(pageErrors).toEqual([])
})

test('resume intent is answered without fake profile data', async ({ page }) => {
  await page.goto('/chat')
  await page.getByLabel('消息输入框').fill('帮我看看简历')
  const sendButton = page.getByRole('button', { name: '发送', exact: true })
  await expect(sendButton).toBeEnabled()
  await sendButton.click()

  const assistant = page.locator('.message-assistant').last()
  await expect(assistant).toHaveText(/\S+/, { timeout: 30_000 })
  await expect(assistant).not.toContainText('您的技能画像为')
  await expect(page.locator('body')).not.toContainText('Mock')
})