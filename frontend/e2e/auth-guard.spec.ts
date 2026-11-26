import { expect, fileUser, test } from './fixtures'

const PROTECTED_PATHS = ['/', '/dashboard', '/chat', '/profile', '/market', '/roadmap']

test.describe('unauthenticated guard', () => {
  for (const path of PROTECTED_PATHS) {
    test(`anonymous visit ${path} lands on login`, async ({ browser }) => {
      const context = await browser.newContext()
      const page = await context.newPage()
      await page.goto(path)
      await expect(page).toHaveURL(/\/login/)
      await expect(
        page.getByRole('heading', { name: '登录 CareerPilot' }),
      ).toBeVisible()
      await context.close()
    })
  }

  test('anonymous reload cannot bypass the guard', async ({ browser }) => {
    const context = await browser.newContext()
    const page = await context.newPage()
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/login/)
    await page.reload()
    await expect(page).toHaveURL(/\/login/)
    await context.close()
  })
})

test.describe('authenticated session lifecycle', () => {
  test('UI register, reload, logout and reload stay consistent', async ({
    browser,
  }) => {
    const context = await browser.newContext()
    const page = await context.newPage()

    const email = `${fileUser('guard-reload')}@e2e.careerpilot.test`
    await page.goto('/register')
    await page.getByLabel('邮箱').fill(email)
    await page.getByLabel('密码', { exact: true }).fill('E2ePassword123')
    await page.getByLabel('确认密码').fill('E2ePassword123')
    await page.getByRole('button', { name: '创建账号' }).click()
    await expect(page).toHaveURL(/\/dashboard/)
    await expect(
      page.getByRole('button', { name: '退出', exact: true }),
    ).toBeVisible()

    await page.reload()
    await expect(page).toHaveURL(/\/dashboard/)
    await expect(
      page.getByRole('button', { name: '退出', exact: true }),
    ).toBeVisible()

    await page.getByRole('button', { name: '退出', exact: true }).click()
    await expect(page).toHaveURL(/\/login/)

    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/login/)

    await context.close()
  })

  test('revoked session redirects protected pages back to login', async ({
    browser,
  }) => {
    const context = await browser.newContext()
    const page = await context.newPage()
    const { createSession } = await import('./fixtures')
    const session = await createSession(context.request, 'guard-revoke')

    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/dashboard/)

    const logoutAll = await session.api.post('/api/auth/logout-all')
    expect(logoutAll.ok()).toBeTruthy()

    await page.goto('/profile')
    await expect(page).toHaveURL(/\/login/)
    await expect(
      page.getByRole('heading', { name: '登录 CareerPilot' }),
    ).toBeVisible()

    await context.close()
  })
})