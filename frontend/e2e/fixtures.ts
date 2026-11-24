import { test, expect } from '@playwright/test'

export type { Page } from '@playwright/test'

function readIdentity(): { runId: string; prefix: string } {
  if (process.env.E2E_TEST_DB_CONFIRMED !== 'true') {
    throw new Error(
      'E2E_TEST_DB_CONFIRMED=true is required; run via the isolated E2E runner',
    )
  }
  const runId = process.env.E2E_RUN_ID?.trim() ?? ''
  if (!runId || !/^[A-Za-z0-9_.-]{1,20}$/.test(runId)) {
    throw new Error('E2E_RUN_ID is required and must be 1-20 safe characters')
  }
  const prefix = (process.env.E2E_USER_PREFIX ?? 'e2e').trim()
  if (
    prefix === 'demo-user' ||
    !/^[A-Za-z0-9_.-]{1,32}$/.test(prefix)
  ) {
    throw new Error('E2E_USER_PREFIX is invalid or points at demo-user')
  }
  return { runId, prefix }
}

export function fileUser(slug: string): string {
  if (!/^[a-z0-9-]{1,24}$/.test(slug)) {
    throw new Error('E2E file slug must be lowercase alphanumeric/dash')
  }
  const { runId, prefix } = readIdentity()
  const user = `${prefix}-${runId}-${slug}`.slice(0, 64)
  if (user === 'demo-user') {
    throw new Error('E2E must never use demo-user')
  }
  return user
}

export function userHeaders(user: string): Record<string, string> {
  return { 'X-User-Id': user }
}

export { expect, test }