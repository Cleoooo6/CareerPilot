import {
  test as base,
  expect,
  type APIRequestContext,
  type APIResponse,
  type Page,
} from '@playwright/test'

export type { Page }
export { expect }
export { base as test }

export interface E2EUser {
  ref: string
  email: string
  displayName: string
  csrfToken: string
}

export interface SessionApi {
  get(path: string): Promise<APIResponse>
  post(path: string, data?: unknown): Promise<APIResponse>
  put(path: string, data?: unknown): Promise<APIResponse>
  patch(path: string, data?: unknown): Promise<APIResponse>
}

export interface E2ESession {
  user: E2EUser
  api: SessionApi
}

const E2E_PASSWORD = 'E2ePassword123'

export function readIdentity(): { runId: string; prefix: string } {
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

function credentials(slug: string): {
  ref: string
  email: string
  password: string
  displayName: string
} {
  const ref = fileUser(slug)
  return {
    ref,
    email: `${ref}@e2e.careerpilot.test`,
    password: E2E_PASSWORD,
    displayName: `E2E ${slug}`,
  }
}

function csrfHeaders(user: E2EUser): Record<string, string> {
  return { 'X-CSRF-Token': user.csrfToken }
}

interface SessionPayload {
  data: { csrf_token: string }
}

export async function createSession(
  request: APIRequestContext,
  slug: string,
): Promise<E2ESession> {
  const cred = credentials(slug)
  const register = await request.post('/api/auth/register', {
    data: {
      email: cred.email,
      password: cred.password,
      display_name: cred.displayName,
    },
  })
  if (!register.ok() && register.status() !== 409) {
    throw new Error(
      `E2E register ${cred.email} failed: HTTP ${register.status()}`,
    )
  }
  let payload: APIResponse = register
  if (!register.ok()) {
    payload = await request.post('/api/auth/login', {
      data: { email: cred.email, password: cred.password },
    })
  }
  if (!payload.ok()) {
    throw new Error(
      `E2E login ${cred.email} failed: HTTP ${payload.status()}`,
    )
  }
  const body = (await payload.json()) as SessionPayload
  const user: E2EUser = {
    ref: cred.ref,
    email: cred.email,
    displayName: cred.displayName,
    csrfToken: body.data.csrf_token,
  }
  const api: SessionApi = {
    get: (path) => request.get(path),
    post: (path, data) =>
      request.post(path, { data: data ?? {}, headers: csrfHeaders(user) }),
    put: (path, data) =>
      request.put(path, { data: data ?? {}, headers: csrfHeaders(user) }),
    patch: (path, data) =>
      request.patch(path, { data: data ?? {}, headers: csrfHeaders(user) }),
  }
  return { user, api }
}

export function useUser(
  slug: string,
  seed?: (session: E2ESession) => Promise<void>,
) {
  return base.extend<{ session: E2ESession }>({
    session: [
      async ({ context }, use) => {
        const session = await createSession(context.request, slug)
        if (seed) await seed(session)
        await use(session)
      },
      { auto: true },
    ],
  })
}