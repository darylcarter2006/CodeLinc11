import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { AppProvider } from '../state/AppContext'

const CLIENT = 'test-client.apps.googleusercontent.com'

const b64url = (v: unknown) => btoa(JSON.stringify(v)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
const token = (claims: Record<string, unknown>) =>
  [b64url({ alg: 'RS256' }), b64url({ iss: 'accounts.google.com', aud: CLIENT, exp: Date.now() / 1000 + 600, email_verified: true, ...claims }), 'sig'].join('.')

// Stand-in for Google's script: renderButton draws a button that "signs in" with `nextToken`.
let nextToken = ''
beforeAll(() => {
  let callback: (r: { credential: string }) => void = () => {}
  window.google = {
    accounts: {
      id: {
        initialize: (config) => {
          callback = config.callback
        },
        renderButton: (parent) => {
          const b = document.createElement('button')
          b.textContent = 'Google account'
          b.onclick = () => callback({ credential: nextToken })
          parent.append(b)
        },
      },
    },
  }
})

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 404 })))
})

afterEach(() => {
  vi.unstubAllEnvs()
})

const renderApp = () =>
  render(
    <MemoryRouter initialEntries={['/auth']}>
      <AppProvider>
        <App />
      </AppProvider>
    </MemoryRouter>,
  )

describe('Google sign-in', () => {
  it('explains when Google sign-in is not set up', async () => {
    // Explicit, so a developer's own VITE_GOOGLE_CLIENT_ID in .env.local can't change the result.
    vi.stubEnv('VITE_GOOGLE_CLIENT_ID', '')
    const user = userEvent.setup()
    renderApp()
    await user.click(await screen.findByRole('button', { name: 'Sign up with Google' }))
    expect(await screen.findByText("Google sign-in isn't set up yet. Use your email for now.")).toHaveAttribute('role', 'alert')
  })

  it('creates an account, and a returning user keeps their saved answers', async () => {
    vi.stubEnv('VITE_GOOGLE_CLIENT_ID', CLIENT)
    const user = userEvent.setup()
    nextToken = token({ email: 'ada@example.com', given_name: 'Ada' })
    const { unmount } = renderApp()

    await user.click(await screen.findByRole('button', { name: 'Google account' }))
    expect(await screen.findByText(/Hi Ada!/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Partner and kids' }))
    await screen.findByText('How many children do you have?')

    await user.click(screen.getByRole('button', { name: /Sign out/ }))
    await user.click(await screen.findByRole('button', { name: 'Google account' }))
    expect(await screen.findByText('Welcome back, Ada. Let\'s pick up where we left off.')).toBeInTheDocument()
    unmount()
  })

  it('rejects a token meant for another app', async () => {
    vi.stubEnv('VITE_GOOGLE_CLIENT_ID', CLIENT)
    const user = userEvent.setup()
    nextToken = token({ email: 'ada@example.com', aud: 'another-app' })
    renderApp()
    await user.click(await screen.findByRole('button', { name: 'Google account' }))
    expect(await screen.findByText(/Google sign-in didn't work\./)).toHaveAttribute('role', 'alert')
  })
})
