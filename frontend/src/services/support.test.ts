import { afterEach, describe, expect, it, vi } from 'vitest'
import { httpSupport, type CallbackRequest } from './support'

const req: CallbackRequest = { name: 'Ada', contactMethod: 'email', contact: 'ada@example.com', bestTime: 'any', topic: 'Help' }

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('httpSupport.requestCallback', () => {
  it('posts to the callback endpoint', async () => {
    const fetch = vi.fn(async () => new Response(null, { status: 201 }))
    vi.stubGlobal('fetch', fetch)
    expect(await httpSupport.requestCallback(req)).toEqual({ ok: true })
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/v1/support/callback-requests')
    expect(JSON.parse(String(init.body))).toEqual(req)
  })

  it.each([
    [404, 'unavailable'],
    [501, 'unavailable'],
    [503, 'unavailable'],
    [422, 'invalid'],
    [500, 'failed'],
    [429, 'failed'],
  ])('maps HTTP %i to %s', async (status, reason) => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status })))
    expect(await httpSupport.requestCallback(req)).toEqual({ ok: false, reason })
  })

  it('treats an unreachable backend as unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('offline'))))
    expect(await httpSupport.requestCallback(req)).toEqual({ ok: false, reason: 'unavailable' })
  })
})
