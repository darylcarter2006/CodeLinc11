import { beforeEach, describe, expect, it } from 'vitest'
import { installFakeServer, type FakeServer } from '../test/fakeServer'
import { authErrorMessage, serverAuth } from './auth'
import { HttpError } from './http'

let server: FakeServer
beforeEach(() => {
  server = installFakeServer()
})

const storedKeys = () => Object.keys(localStorage)

describe('server accounts', () => {
  it('signs up on the server and keeps only the token and display details in the browser', async () => {
    const result = await serverAuth.signUp('Riley', 'riley@example.com', 'correct horse')
    expect(result).toEqual({ ok: true, account: { name: 'Riley', email: 'riley@example.com', hasPassword: true } })
    expect(serverAuth.current()?.email).toBe('riley@example.com')
    expect(serverAuth.token()).toMatch(/^[0-9a-f]{64}$/)
    expect(storedKeys()).toEqual(['cc-auth'])
    expect(localStorage.getItem('cc-auth')).not.toContain('correct horse')
    const [url, init] = server.fetch.mock.calls[0]
    expect(url).toBe('/v1/auth/signup')
    expect(JSON.parse(String(init?.body))).toEqual({ name: 'Riley', email: 'riley@example.com', password: 'correct horse' })
  })

  it('logs in with the right password only', async () => {
    await serverAuth.signUp('Riley', 'riley@example.com', 'correct horse')
    serverAuth.forget()
    expect(await serverAuth.logIn('riley@example.com', 'wrong password')).toEqual({
      ok: false,
      error: "That email and password don't match. Try again, or reset your password.",
    })
    expect(serverAuth.current()).toBeNull()
    expect((await serverAuth.logIn('riley@example.com', 'correct horse')).ok).toBe(true)
  })

  it('reports an email that already has an account', async () => {
    await serverAuth.signUp('Riley', 'riley@example.com', 'correct horse')
    const again = await serverAuth.signUp('Riley', 'riley@example.com', 'another one')
    expect(again).toEqual({ ok: false, error: 'An account with this email already exists. Log in instead.' })
  })

  it('treats an expired token as signed out', () => {
    localStorage.setItem(
      'cc-auth',
      JSON.stringify({ token: 'a'.repeat(64), expiresAt: new Date(Date.now() - 1000).toISOString(), account: { name: 'R', email: 'r@example.com', hasPassword: true } }),
    )
    expect(serverAuth.current()).toBeNull()
    expect(serverAuth.token()).toBeNull()
  })

  it('forget() clears this browser, and revoke() tells the server', async () => {
    await serverAuth.signUp('Riley', 'riley@example.com', 'correct horse')
    const token = serverAuth.token()!
    serverAuth.forget()
    expect(storedKeys()).toEqual([])
    await serverAuth.revoke(token)
    const [, init] = server.fetch.mock.calls.find(([u]) => u === '/v1/auth/logout')!
    expect(new Headers(init?.headers).get('Authorization')).toBe(`Bearer ${token}`)
    expect(server.tokens.has(token)).toBe(false)
  })

  it('changes the password when the current one is right', async () => {
    await serverAuth.signUp('Riley', 'riley@example.com', 'correct horse')
    expect(await serverAuth.changePassword('not it', 'a new phrase')).toEqual({ ok: false, error: "Your current password isn't right." })
    expect(await serverAuth.changePassword('correct horse', 'a new phrase')).toEqual({ ok: true })
    serverAuth.forget()
    expect((await serverAuth.logIn('riley@example.com', 'a new phrase')).ok).toBe(true)
  })

  it('asks for a reset link the same way whether or not the account exists, then resets', async () => {
    await serverAuth.signUp('Riley', 'riley@example.com', 'correct horse')
    serverAuth.forget()
    expect(await serverAuth.requestPasswordReset('nobody@example.com')).toEqual({ ok: true })
    expect(await serverAuth.requestPasswordReset('riley@example.com')).toEqual({ ok: true })
    const [{ token }] = server.sentResets
    expect((await serverAuth.resetPassword(token, 'a new phrase')).ok).toBe(true)
    expect(serverAuth.current()?.email).toBe('riley@example.com')
    expect((await serverAuth.resetPassword(token, 'again please')).ok).toBe(false)
  })
})

describe('authErrorMessage', () => {
  it.each([
    [new HttpError(0, 'network_error', 'x'), "We couldn't reach Coverage Compass. Check your connection and try again."],
    [new HttpError(404, 'not_found', 'x'), "We couldn't reach Coverage Compass. Check your connection and try again."],
    [new HttpError(429, 'rate_limited', 'x'), 'Too many attempts. Wait a few minutes and try again.'],
    [new HttpError(401, 'invalid_credential', 'x'), "Google sign-in didn't work. Try again, or use your email instead."],
    [new HttpError(422, 'weak_password', 'That password is too easy to guess.'), 'That password is too easy to guess.'],
    [new HttpError(500, 'internal_error', 'Traceback: secret detail'), 'Something went wrong. Please try again.'],
    [new Error('boom'), 'Something went wrong. Please try again.'],
  ])('%s', (error, message) => {
    expect(authErrorMessage(error)).toBe(message)
  })

  it('does not show server text for codes it does not know', () => {
    expect(authErrorMessage(new HttpError(400, 'something_new', '<b>raw</b>'))).toBe('Something went wrong. Please try again.')
  })
})
