import type {
  ApiEnvelope,
  ApiErrorEnvelope,
} from '@/types/chat'

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

export async function requestJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...(init.headers ?? {}),
      },
    })
  } catch (error) {
    throw new ApiError(0, 'NETWORK_ERROR', '无法连接后端服务', error)
  }

  if (!response.ok) {
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