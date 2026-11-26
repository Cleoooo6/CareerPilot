import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Router } from 'vue-router'

const getMeMock = vi.fn()

vi.mock('@/api/auth', () => ({
  getMe: (...args: unknown[]) => getMeMock(...args),
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  requestPasswordReset: vi.fn(),
  confirmPasswordReset: vi.fn(),
}))

import { authStore } from '@/stores/auth'
import { router } from '@/router/index'

const USER = {
  id: '00000000-0000-0000-0000-000000000001',
  email: 'guard@example.com',
  display_name: 'Guard Tester',
  status: 'active',
  email_verified: false,
  is_demo: false,
}

function isRouter(value: unknown): value is Router {
  return typeof value === 'object' && value !== null && 'push' in value
}

describe('router auth guard', () => {
  beforeEach(() => {
    getMeMock.mockReset()
    authStore.clear()
    authStore.status = 'unknown'
  })

  it('redirects anonymous dashboard access to login', async () => {
    expect(isRouter(router)).toBe(true)
    getMeMock.mockRejectedValue(new Error('401'))
    await router.push('/dashboard')
    expect(router.currentRoute.value.name).toBe('login')
    expect(router.currentRoute.value.query.redirect).toBe('/dashboard')
    expect(getMeMock).toHaveBeenCalledTimes(1)
  })

  it('keeps an authenticated user on the requested page after refresh-like navigation', async () => {
    getMeMock.mockResolvedValue(USER)
    await router.push('/dashboard')
    expect(router.currentRoute.value.name).toBe('dashboard')
    expect(authStore.status).toBe('authenticated')
  })

  it('does not call /me for public routes', async () => {
    await router.push('/login')
    expect(router.currentRoute.value.name).toBe('login')
    expect(getMeMock).not.toHaveBeenCalled()
  })

  it('sends the root redirect through the guard as well', async () => {
    getMeMock.mockRejectedValue(new Error('401'))
    await router.push('/')
    expect(router.currentRoute.value.name).toBe('login')
  })

  it('blocks direct deep links once the session is anonymous', async () => {
    authStore.status = 'anonymous'
    await router.push('/profile')
    expect(router.currentRoute.value.name).toBe('login')
    expect(getMeMock).not.toHaveBeenCalled()
  })
})