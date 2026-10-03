import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { localAuth } from '../services/auth'
import { storage } from '../services/storage'
import { AppProvider } from '../state/AppContext'
import { useApp } from '../state/context'

/* Backend side of Google sign-in: token exchange, session, sign-out. The button lives elsewhere. */

const HOUR = 3600_000
const TOKEN = 'a'.repeat(64)

const signInResponse = (overrides: Record<string, unknown> = {}) => ({
  access_token: TOKEN,
  expires_at: new Date(Date.now() + HOUR).toISOString(),
  user: { id: 'usr_1', email: 'jordan@example.com', name: 'Jordan Lee', given_name: 'Jordan', picture: null },
  ...overrides,
})

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn(async (url: string) => (url.endsWith('/v1/auth/google') ? json(signInResponse()) : new Response(null, { status: 204 })))
  vi.stubGlobal('fetch', fetchMock)
})

describe('Google sign-in service', () => {
  it('exchanges the credential and stores the account', async () => {
    const result = await localAuth.signInWithGoogle('google-id-token')
    expect(result).toEqual({ ok: true, account: { name: 'Jordan', email: 'jordan@example.com', provider: 'google' } })
    expect(localAuth.current()?.email).toBe('jordan@example.com')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/v1/auth/google')
    expect(JSON.parse(init.body)).toEqual({ credential: 'google-id-token' })
  })

  it.each([
    [401, "Google sign-in couldn't be verified. Please try again."],
    [429, 'Too many sign-in attempts. Wait a minute and try again.'],
    [503, 'Google sign-in is not available right now. Try again later.'],
  ])('turns a %i into a readable error', async (status, message) => {
    fetchMock.mockImplementation(async () => json({ error: { code: 'x', message: 'x' } }, status))
    expect(await localAuth.signInWithGoogle('cred')).toEqual({ ok: false, error: message })
    expect(localAuth.current()).toBeNull()
  })

  it('reports an unreachable server', async () => {
    fetchMock.mockImplementation(async () => {
      throw new TypeError('Failed to fetch')
    })
    const result = await localAuth.signInWithGoogle('cred')
    expect(result.ok).toBe(false)
    expect(!result.ok && result.error).toMatch(/couldn't reach the server/)
  })

  it('signs out locally and revokes the token on the server', async () => {
    await localAuth.signInWithGoogle('cred')
    localAuth.signOut()
    expect(localAuth.current()).toBeNull()
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/v1/auth/logout', expect.anything()))
    const [, init] = fetchMock.mock.calls.find(([u]) => u === '/v1/auth/logout')!
    expect(init.headers.Authorization).toBe(`Bearer ${TOKEN}`)
  })

  it('treats an expired token as signed out', async () => {
    fetchMock.mockImplementation(async () => json(signInResponse({ expires_at: new Date(Date.now() - 1000).toISOString() })))
    await localAuth.signInWithGoogle('cred')
    expect(localAuth.current()).toBeNull()
  })

  it('a Google account cannot be logged into with the email form', async () => {
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

describe('app state', () => {
  it('does not show one person’s saved profile to a different Google account', async () => {
    storage.set('account', { name: 'Maya', email: 'maya@example.com' })
    storage.set('profile', { p: { income: 78000 }, known: ['income'], confirmed: true, updated: 1 })
    render(
      <AppProvider>
        <SignInProbe />
      </AppProvider>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Google' }))
    expect(await screen.findByText('jordan@example.com')).toBeInTheDocument()
    expect(storage.get<{ confirmed: boolean }>('profile')?.confirmed).toBe(false)
  })

  it('keeps the profile when the same account signs back in', async () => {
    storage.set('account', { name: 'Jordan', email: 'jordan@example.com', provider: 'google' })
    storage.set('profile', { p: { income: 78000 }, known: ['income'], confirmed: true, updated: 1 })
    render(
      <AppProvider>
        <SignInProbe />
      </AppProvider>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Google' }))
    expect(await screen.findByText('jordan@example.com')).toBeInTheDocument()
    expect(storage.get<{ confirmed: boolean }>('profile')?.confirmed).toBe(true)
  })
})
