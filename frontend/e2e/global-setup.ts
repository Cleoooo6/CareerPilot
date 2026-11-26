import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { request as playwrightRequest } from '@playwright/test'

interface MarketFixture {
  source: {
    name: string
    source_type: string
    dataset_kind: string
    license_note: string
    base_url: string | null
  }
  jobs: Array<Record<string, unknown>>
}

const FIXTURE_USER = 'e2e-market-seeder'
const FIXTURE_EMAIL = `${FIXTURE_USER}@e2e.careerpilot.test`
const FIXTURE_PASSWORD = 'E2ePassword123'

export default async function globalSetup(): Promise<void> {
  const baseUrl = process.env.E2E_BASE_URL?.trim() ?? ''
  if (!baseUrl) {
    throw new Error('E2E_BASE_URL is required for isolated E2E')
  }
  if (process.env.E2E_TEST_DB_CONFIRMED !== 'true') {
    throw new Error(
      'Refusing E2E: E2E_TEST_DB_CONFIRMED=true was not set by the isolated runner',
    )
  }
  if (!process.env.E2E_RUN_ID?.trim()) {
    throw new Error('E2E_RUN_ID is required for isolated E2E')
  }
  if (/:5180\b|127\.0\.0\.1:5180|localhost:5180/.test(baseUrl)) {
    throw new Error('Refusing E2E against the formal 5180 environment')
  }

  const fixture: MarketFixture = JSON.parse(
    readFileSync(
      join(process.cwd(), 'e2e', 'fixtures', 'market-synthetic-jobs.json'),
      'utf-8',
    ),
  )

  const context = await playwrightRequest.newContext({ baseURL: baseUrl })
  try {
    const register = await context.post('/api/auth/register', {
      data: {
        email: FIXTURE_EMAIL,
        password: FIXTURE_PASSWORD,
        display_name: 'E2E Market Seeder',
      },
    })
    if (!register.ok() && register.status() !== 409) {
      throw new Error(`E2E seeder register failed: HTTP ${register.status()}`)
    }
    let payload = register
    if (!register.ok()) {
      payload = await context.post('/api/auth/login', {
        data: { email: FIXTURE_EMAIL, password: FIXTURE_PASSWORD },
      })
    }
    if (!payload.ok()) {
      throw new Error(`E2E seeder login failed: HTTP ${payload.status()}`)
    }
    const session = (await payload.json()) as {
      data: { csrf_token: string }
    }

    const response = await context.post('/api/market/import', {
      headers: { 'X-CSRF-Token': session.data.csrf_token },
      data: fixture,
    })
    if (!response.ok()) {
      throw new Error(
        `E2E market fixture import failed: HTTP ${response.status()}`,
      )
    }
    const body = (await response.json()) as {
      data: { total: number; imported: number; duplicates: number; failed: number }
    }
    if (
      body.data.total !== fixture.jobs.length ||
      body.data.failed !== 0 ||
      body.data.imported + body.data.duplicates !== fixture.jobs.length
    ) {
      throw new Error('E2E market fixture import returned an unexpected result')
    }
  } finally {
    await context.dispose()
  }
}