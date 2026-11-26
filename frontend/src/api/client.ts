import type {
  ApiEnvelope,
  ApiErrorEnvelope,
} from '@/types/chat'

const CSRF_COOKIE = 'cp_csrf'
const CSRF_HEADER = 'X-CSRF-Token'
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])
const UNAUTHORIZED_EVENT = 'careerpilot:unauthorized'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly detail: unknown

  constructor(status: number, code: string, message: string, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.detail = detail
  }
}

export function isAbortError(error: unknown): boolean {
  return (
    (error instanceof DOMException && error.name === 'AbortError') ||
    (error instanceof Error && error.name === 'AbortError')
  )
}

function readCookie(name: string): string | null {
  if (typeof document === 'undefined' || !document.cookie) return null
  const prefix = `${name}=`
  for (const part of document.cookie.split(';')) {
    const item = part.trim()
    if (item.startsWith(prefix)) {
      return decodeURIComponent(item.slice(prefix.length))
    }
  }
  return null
}

export function csrfHeaders(method: string | undefined): Record<string, string> {
  const verb = (method ?? 'GET').toUpperCase()
  if (SAFE_METHODS.has(verb)) return {}
  const token = readCookie(CSRF_COOKIE)
  return token ? { [CSRF_HEADER]: token } : {}
}

export function notifyUnauthorized(status: number): void {
  if (status === 401 && typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT))
  }
}

async function readError(response: Response): Promise<ApiError> {
  let detail: unknown = null
  try {
    const body = (await response.json()) as ApiErrorEnvelope
    if (body && body.error) {
      return new ApiError(
        response.status,
        body.error.code,
        body.error.message,
        body.error.details,
      )
    }
    detail = body
  } catch {
    detail = null
  }
  return new ApiError(response.status, 'HTTP_ERROR', `请求失败（HTTP ${response.status}）`, detail)
}

export async function requestForm<T>(
  path: string,
  formData: FormData,
  init: RequestInit = {},
): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      method: 'POST',
      ...init,
      credentials: 'include',
      headers: {
        ...csrfHeaders(init.method ?? 'POST'),
        ...(init.headers ?? {}),
      },
      body: formData,
    })
  } catch (error) {
    throw new ApiError(0, 'NETWORK_ERROR', '无法连接后端服务', error)
  }
  if (!response.ok) {
    notifyUnauthorized(response.status)
    throw await readError(response)
  }
  const body = (await response.json()) as ApiEnvelope<T> | ApiErrorEnvelope
  if (!body || body.ok !== true) {
    if (body && 'error' in body) {
      throw new ApiError(
        response.status,
        body.error.code,
        body.error.message,
        body.error.details,
      )
    }
    throw new ApiError(response.status, 'INVALID_RESPONSE', '后端返回结构不合法')
  }
  return body.data
}

export async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      ...init,
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...csrfHeaders(init.method),
        ...(init.headers ?? {}),
      },
    })
  } catch (error) {
    throw new ApiError(0, 'NETWORK_ERROR', '无法连接后端服务', error)
  }

  if (!response.ok) {
    notifyUnauthorized(response.status)
    throw await readError(response)
  }
  if (response.status === 204) {
    return undefined as T
  }
  const body = (await response.json()) as ApiEnvelope<T> | ApiErrorEnvelope
  if (!body || body.ok !== true) {
    if (body && 'error' in body) {
      throw new ApiError(
        response.status,
        body.error.code,
        body.error.message,
        body.error.details,
      )
    }
    throw new ApiError(response.status, 'INVALID_RESPONSE', '后端返回结构不合法')
  }
  return body.data
}