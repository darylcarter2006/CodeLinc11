import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { localAuth } from '../services/auth'
import { storage } from '../services/storage'
import { AppProvider } from '../state/AppContext'
import { useApp } from '../state/context'

/*
 * Google sign-in through the backend (/v1/auth/google verifies the token's signature).
 * The no-backend fallback and the button itself are covered in google.test.tsx.
 */

const CLIENT = 'test-client.apps.googleusercontent.com'
const HOUR = 3600_000
const TOKEN = 'a'.repeat(64)

const b64url = (v: unknown) => btoa(JSON.stringify(v)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
/** An unsigned token: only acceptable on the no-backend path, which reads claims. */
const unsignedToken = (email: string) =>
  [b64url({ alg: 'RS256' }), b64url({ iss: 'accounts.google.com', aud: CLIENT, exp: Date.now() / 1000 + 600, email_verified: true, email, given_name: 'Ada' }), 'sig'].join('.')

const serverUser = (email = 'jordan@example.com') => ({
  access_token: TOKEN,
  expires_at: new Date(Date.now() + HOUR).toISOString(),
  user: { id: 'usr_1', email, name: 'Jordan Lee', given_name: 'Jordan', picture: null },
})

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const apiError = (status: number, code: string) => json({ error: { code, message: code } }, status)

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn(async (url: string) => (url.endsWith('/v1/auth/google') ? json(serverUser()) : new Response(null, { status: 204 })))
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllEnvs()
})

describe('backend-verified Google sign-in', () => {
  it('sends the credential to the backend and stores the verified account', async () => {
    const result = await localAuth.signInWithGoogle('google-id-token')
    expect(result).toEqual({ ok: true, isNew: true, account: { name: 'Jordan', email: 'jordan@example.com', provider: 'google' } })
    expect(localAuth.current()?.provider).toBe('google')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/v1/auth/google')
    expect(JSON.parse(init.body)).toEqual({ credential: 'google-id-token' })
  })

  it.each([
    [401, 'invalid_credential', "Google sign-in didn't work. Try again, or use your email instead."],
    [429, 'rate_limited', 'Too many sign-in attempts. Wait a minute and try again.'],
    [503, 'auth_provider_unreachable', "We couldn't reach Google to check your sign-in. Try again in a moment."],
  ])('a %i (%s) is an error and never falls back to the browser-only path', async (status, code, message) => {
    vi.stubEnv('VITE_GOOGLE_CLIENT_ID', CLIENT)
    fetchMock.mockImplementation(async () => apiError(status, code))
    expect(await localAuth.signInWithGoogle(unsignedToken('ada@example.com'))).toEqual({ ok: false, error: message })
    expect(localAuth.current()).toBeNull()
  })

  it.each([
    ['the endpoint is missing (404)', async () => new Response(null, { status: 404 })],
    // What static hosts such as Amplify/CloudFront answer to a POST when no backend is deployed.
    ['a static host refuses the POST (403)', async () => new Response('<Error>AccessDenied</Error>', { status: 403, headers: { 'Content-Type': 'application/xml' } })],
    ['a static host rejects the method (405)', async () => new Response('<html>Method Not Allowed</html>', { status: 405, headers: { 'Content-Type': 'text/html' } })],
    ['a static host serves the app page (200 HTML)', async () => new Response('<!doctype html><html></html>', { status: 200, headers: { 'Content-Type': 'text/html' } })],
    ['something answers 200 JSON that is not a sign-in result', async () => json({ ok: true })],
    ['an older backend without sign-in (404 envelope)', async () => apiError(404, 'not_found')],
    ['Google sign-in is not configured (503 auth_unavailable)', async () => apiError(503, 'auth_unavailable')],
    [
      'the backend is unreachable',
      async () => {
        throw new TypeError('Failed to fetch')
      },
    ],
  ])('falls back to a browser-only account when %s', async (_, response) => {
    vi.stubEnv('VITE_GOOGLE_CLIENT_ID', CLIENT)
    fetchMock.mockImplementation(response)
    const result = await localAuth.signInWithGoogle(unsignedToken('ada@example.com'))
    expect(result).toEqual({ ok: true, isNew: true, account: { name: 'Ada', email: 'ada@example.com' } })
    expect(storage.get('token')).toBeNull()
  })

  it('signs out locally and revokes the token on the server', async () => {
    await localAuth.signInWithGoogle('cred')
    localAuth.signOut()
    expect(localAuth.current()).toBeNull()
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/v1/auth/logout', expect.anything()))
    const [, init] = fetchMock.mock.calls.find(([u]) => u === '/v1/auth/logout')!
    expect(init.headers.Authorization).toBe(`Bearer ${TOKEN}`)
  })

  it('treats an expired account token as signed out', async () => {
    fetchMock.mockImplementation(async () => json({ ...serverUser(), expires_at: new Date(Date.now() - 1000).toISOString() }))
    await localAuth.signInWithGoogle('cred')
    expect(localAuth.current()).toBeNull()
  })

  it('a verified Google account cannot be opened with the email form', async () => {
    await localAuth.signInWithGoogle('cred')
    localAuth.signOut()
    expect(localAuth.logIn('jordan@example.com', 'any-password').ok).toBe(false)
  })
})

function SignInProbe() {
  const { signInWithGoogle, account } = useApp()
  return (
    <>
      <button onClick={() => void signInWithGoogle('cred')}>Google</button>
      <output>{account?.email ?? 'signed out'}</output>
    </>
  )
}

const renderProbe = () =>
  render(
    <AppProvider>
      <SignInProbe />
    </AppProvider>,
  )

describe('profiles on a shared browser', () => {
  it('a different Google account starts fresh instead of seeing the previous profile', async () => {
    storage.set('account', { name: 'Maya', email: 'maya@example.com' })
    storage.set('profile', { p: { income: 78000 }, known: ['income'], confirmed: true, updated: 1 })
    renderProbe()
    await userEvent.click(screen.getByRole('button', { name: 'Google' }))
    expect(await screen.findByText('jordan@example.com')).toBeInTheDocument()
    expect(storage.get<{ confirmed: boolean }>('profile')?.confirmed).toBe(false)
  })

  it('the same account signing back in keeps its profile', async () => {
    storage.set('account', { name: 'Jordan', email: 'jordan@example.com', provider: 'google' })
    storage.set('profile', { p: { income: 78000 }, known: ['income'], confirmed: true, updated: 1 })
    renderProbe()
    await userEvent.click(screen.getByRole('button', { name: 'Google' }))
    expect(await screen.findByText('jordan@example.com')).toBeInTheDocument()
    expect(storage.get<{ confirmed: boolean }>('profile')?.confirmed).toBe(true)
  })
})
