import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { AppProvider } from '../state/AppContext'
import { installFakeServer } from './fakeServer'

const CLIENT = 'test-client.apps.googleusercontent.com'

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

// The fake backend accepts credentials of the form "good:<sub>:<email>" (the real one verifies Google's signature).
beforeEach(() => {
  installFakeServer()
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
    nextToken = 'good:sub-ada:ada@example.com'
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

  it('shows an error when the server rejects the Google token', async () => {
    vi.stubEnv('VITE_GOOGLE_CLIENT_ID', CLIENT)
    const user = userEvent.setup()
    nextToken = 'forged-or-expired-token'
    renderApp()
    await user.click(await screen.findByRole('button', { name: 'Google account' }))
    expect(await screen.findByText(/Google sign-in didn't work\./)).toHaveAttribute('role', 'alert')
  })

  it('never signs in without the server, even with a well-formed token', async () => {
    vi.stubEnv('VITE_GOOGLE_CLIENT_ID', CLIENT)
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('offline'))))
    const user = userEvent.setup()
    nextToken = 'good:sub-ada:ada@example.com'
    renderApp()
    await user.click(await screen.findByRole('button', { name: 'Google account' }))
    expect(await screen.findByText(/couldn't reach Coverage Compass/)).toHaveAttribute('role', 'alert')
    expect(screen.queryByText(/Hi Ada!/)).not.toBeInTheDocument()
  })
})
