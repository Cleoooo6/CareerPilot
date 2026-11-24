import { readFileSync } from 'node:fs'
import { join } from 'node:path'

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
  const response = await fetch(`${baseUrl}/api/market/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(fixture),
  })
  if (!response.ok) {
    throw new Error(`E2E market fixture import failed: HTTP ${response.status}`)
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

  }