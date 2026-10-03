import { describe, expect, it } from 'vitest'
import { readGoogleCredential } from './google'

const CLIENT = 'test-client.apps.googleusercontent.com'
const NOW = Date.UTC(2026, 9, 3)

const b64url = (v: unknown) => btoa(JSON.stringify(v)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
const fakeToken = (claims: Record<string, unknown>) =>
  [b64url({ alg: 'RS256' }), b64url({ iss: 'https://accounts.google.com', aud: CLIENT, exp: NOW / 1000 + 600, email_verified: true, ...claims }), 'sig'].join('.')

describe('readGoogleCredential', () => {
  it('reads first name and lower-cased email', () => {
    const token = fakeToken({ email: 'Ada@Example.com', given_name: 'Ada', name: 'Ada Lovelace' })
    expect(readGoogleCredential(token, CLIENT, NOW)).toEqual({ email: 'ada@example.com', name: 'Ada' })
  })

  it('falls back to the full name, then the email prefix', () => {
    expect(readGoogleCredential(fakeToken({ email: 'a@x.com', name: 'Ada L' }), CLIENT, NOW)?.name).toBe('Ada L')
    expect(readGoogleCredential(fakeToken({ email: 'ada@x.com' }), CLIENT, NOW)?.name).toBe('ada')
  })

  it.each([
    ['another app', { aud: 'someone-else' }],
    ['a different issuer', { iss: 'https://evil.example.com' }],
    ['an expired token', { exp: NOW / 1000 - 1 }],
    ['an unverified email', { email_verified: false }],
    ['a missing email', { email: undefined }],
  ])('rejects %s', (_, claims) => {
    expect(readGoogleCredential(fakeToken({ email: 'ada@x.com', ...claims }), CLIENT, NOW)).toBeNull()
  })

  it('rejects malformed tokens', () => {
    expect(readGoogleCredential('not-a-jwt', CLIENT, NOW)).toBeNull()
    expect(readGoogleCredential('a.b.c', CLIENT, NOW)).toBeNull()
  })
})
