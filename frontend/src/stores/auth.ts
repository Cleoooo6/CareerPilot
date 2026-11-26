import { reactive } from 'vue'

import {
  getMe,
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister,
} from '@/api/auth'
import type { AuthSessionDto, AuthUserDto } from '@/types/auth'

export type AuthStatus = 'unknown' | 'authenticated' | 'anonymous'

interface AuthState {
  user: AuthUserDto | null
  status: AuthStatus
  pending: boolean
}

const state = reactive<AuthState>({
  user: null,
  status: 'unknown',
  pending: false,
})

let bootstrapPromise: Promise<void> | null = null

async function bootstrap(force = false): Promise<void> {
  if (!force && state.status !== 'unknown') return
  if (bootstrapPromise && !force) return bootstrapPromise

  bootstrapPromise = (async () => {
    state.pending = true
    try {
      state.user = await getMe()
      state.status = 'authenticated'
    } catch {
      state.user = null
      state.status = 'anonymous'
    } finally {
      state.pending = false
      bootstrapPromise = null
    }
  })()
  return bootstrapPromise
}

function applySession(session: AuthSessionDto): AuthSessionDto {
  state.user = session.user
  state.status = 'authenticated'
  return session
}

async function login(email: string, password: string): Promise<AuthSessionDto> {
  return applySession(await apiLogin(email, password))
}

async function register(
  email: string,
  password: string,
  displayName?: string,
): Promise<AuthSessionDto> {
  return applySession(await apiRegister(email, password, displayName))
}

async function logout(): Promise<void> {
  try {
    await apiLogout()
  } finally {
    clear()
  }
}

function clear(): void {
  state.user = null
  state.status = 'anonymous'
}

export const authStore = Object.assign(state, {
  bootstrap,
  login,
  register,
  logout,
  clear,
})

export function useAuthStore() {
  return authStore
}