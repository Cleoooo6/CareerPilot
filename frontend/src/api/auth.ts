import { requestJson } from './client'
import type { AuthMessageDto, AuthSessionDto, AuthUserDto } from '@/types/auth'

export function getMe(): Promise<AuthUserDto> {
  return requestJson<AuthUserDto>('/api/auth/me')
}

export function login(email: string, password: string): Promise<AuthSessionDto> {
  return requestJson<AuthSessionDto>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
}

export function register(
  email: string,
  password: string,
  displayName?: string,
): Promise<AuthSessionDto> {
  return requestJson<AuthSessionDto>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, display_name: displayName ?? null }),
  })
}

export function logout(): Promise<AuthMessageDto> {
  return requestJson<AuthMessageDto>('/api/auth/logout', { method: 'POST' })
}

export function requestPasswordReset(email: string): Promise<AuthMessageDto> {
  return requestJson<AuthMessageDto>('/api/auth/password-reset/request', {
    method: 'POST',
    body: JSON.stringify({ email }),
  })
}

export function confirmPasswordReset(
  token: string,
  newPassword: string,
): Promise<AuthMessageDto> {
  return requestJson<AuthMessageDto>('/api/auth/password-reset/confirm', {
    method: 'POST',
    body: JSON.stringify({ token, new_password: newPassword }),
  })
}