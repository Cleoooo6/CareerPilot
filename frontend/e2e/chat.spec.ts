import { expect, fileUser, test } from './fixtures'

const USER = fileUser('chat')
test.use({ extraHTTPHeaders: { 'X-User-Id': USER } })

test('chat workbench streams through real API and SSE', async ({ page }) => {
  const pageErrors: string[] = []
  page.on('pageerror', (error) => pageErrors.push(error.message))

  await page.goto('/chat')
  await expect(
    page.getByRole('heading', { level: 2, name: /AI Career Advisor/ }),
  ).toBeVisible()
  await expect(page.locator('.chat-empty')).toBeVisible()
  await expect(page.locator('.chat-head-actions .tag')).toHaveText('演示模式', {
    timeout: 10_000,
  })

  await page.getByRole('button', { name: '梳理职业方向' }).click()
  await expect(page.getByLabel('消息输入框')).toHaveValue(/我还不确定适合什么方向/)

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

test('history failure exposes retry and a clean new conversation', async ({
  page,
}) => {
  await page.addInitScript(() => {
    localStorage.setItem(
      'careerpilot:conversation_id',
      '00000000-0000-0000-0000-000000000000',
    )
  })
  await page.route('**/api/conversations/*/messages', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({
          ok: false,
          error: { code: 'TEST_HISTORY_ERROR', message: '历史消息读取失败' },
          request_id: 'test',
        }),
      })
      return
    }
    await route.continue()
  })

  await page.goto('/chat')
  await expect(page.getByText('历史消息加载失败')).toBeVisible({
    timeout: 15_000,
  })
  await expect(
    page.getByRole('button', { name: '重试加载历史' }),
  ).toBeVisible()
  await page.getByRole('button', { name: '开始新对话' }).click()
  await expect(page.locator('.chat-empty')).toBeVisible()
  await expect(page.getByRole('button', { name: '梳理职业方向' })).toBeVisible()
})
