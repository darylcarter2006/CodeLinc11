import { afterEach, describe, expect, it, vi } from 'vitest'
import { HttpError, postJson } from './http'

afterEach(() => {
  vi.unstubAllGlobals()
})

const reply = (status: number, contentType?: string, body = '') =>
  vi.stubGlobal('fetch', vi.fn(async () => new Response(body || null, { status, headers: contentType ? { 'Content-Type': contentType } : {} })))

describe('postJson', () => {
  it('returns API responses', async () => {
    reply(200, 'text/plain; charset=utf-8', 'hello')
    expect(await (await postJson('/ai/chat', {})).text()).toBe('hello')
  })

  it('treats an HTML page (a static host fallback) as not found', async () => {
    reply(200, 'text/html; charset=utf-8', '<!doctype html><title>Coverage Compass</title>')
    await expect(postJson('/support/callback-requests', {})).rejects.toMatchObject({ status: 404, code: 'not_found' })
  })

  it('reads the error envelope', async () => {
    reply(429, 'application/json', JSON.stringify({ error: { code: 'rate_limited', message: 'Slow down' } }))
    const err = await postJson('/ai/chat', {}).catch((e: unknown) => e)
    expect(err).toBeInstanceOf(HttpError)
    expect(err).toMatchObject({ status: 429, code: 'rate_limited', message: 'Slow down' })
  })

  it('reports an unreachable server as status 0', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('offline'))))
    await expect(postJson('/ai/chat', {})).rejects.toMatchObject({ status: 0, code: 'network_error' })
  })
})
