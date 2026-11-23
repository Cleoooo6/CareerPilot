import { describe, expect, it, vi } from 'vitest'

import { ApiError, requestJson } from '@/api/client'

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('requestJson', () => {
  it('returns the data field from a successful envelope', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({ ok: true, data: { value: 1 }, request_id: 'r1' }),
      ),
    )
    await expect(requestJson<{ value: number }>('/api/x')).resolves.toEqual({
      value: 1,
    })
  })

  it('throws a typed ApiError for an error envelope', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            ok: false,
            error: { code: 'NOT_FOUND', message: '不存在', details: {} },
            request_id: 'r1',
          },
          404,
        ),
      ),
    )
    await expect(requestJson('/api/x')).rejects.toMatchObject({
      status: 404,
      code: 'NOT_FOUND',
      message: '不存在',
    })
  })

  it('throws NETWORK_ERROR when fetch rejects', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
    const error = await requestJson('/api/x').catch((value: unknown) => value)
    expect(error).toBeInstanceOf(ApiError)
    expect((error as ApiError).code).toBe('NETWORK_ERROR')
  })

  it('returns undefined for 204', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(null, { status: 204 })))
    await expect(requestJson('/api/x')).resolves.toBeUndefined()
  })

  it('throws INVALID_RESPONSE for a non-envelope body', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ value: 1 })))
    await expect(requestJson('/api/x')).rejects.toMatchObject({
      code: 'INVALID_RESPONSE',
    })
  })
})