import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import App from '../App'
import { EXAMPLE, FLOW } from '../domain/profile'
import { AppProvider } from '../state/AppContext'
import { installFakeServer, type FakeServer } from './fakeServer'

let server: FakeServer
beforeEach(() => {
  server = installFakeServer()
})

const renderApp = (path = '/') =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <AppProvider>
        <App />
      </AppProvider>
    </MemoryRouter>,
  )

/** An account that finished onboarding on another device: created and saved through the API. */
async function existingAccount(email = 'maya@example.com', password = 'long-enough') {
  const res = await fetch('/v1/auth/signup', { method: 'POST', body: JSON.stringify({ name: 'Maya', email, password }) })
  const { access_token } = await res.json()
  const state = {
    saved: { p: EXAMPLE, known: FLOW.map((f) => f.k), confirmed: true, updated: 1 },
    log: [{ at: 1, text: 'Created your profile in the onboarding chat' }],
    steps: {},
    policySeen: 'term',
  }
  await fetch('/v1/account/profile', { method: 'PUT', body: JSON.stringify(state), headers: { Authorization: `Bearer ${access_token}` } })
  server.fetch.mockClear()
}

/** The "Log in" tab, then the form's "Log in" submit button. */
async function logIn(user: ReturnType<typeof userEvent.setup>, email = 'maya@example.com', password = 'long-enough') {
  const tabs = within(await screen.findByRole('group', { name: 'Sign up or log in' }))
  await user.click(tabs.getByRole('button', { name: 'Log in' }))
  await user.type(screen.getByLabelText('Email'), email)
  await user.type(screen.getByLabelText('Password'), password)
  const submit = screen.getAllByRole('button', { name: 'Log in' }).find((b) => b.getAttribute('type') === 'submit')!
  await user.click(submit)
}

describe('accounts on the server', () => {
  it('logging in on a new device loads the saved answers, and nothing financial is kept in the browser', async () => {
    await existingAccount()
    const user = userEvent.setup()
    renderApp()
    await logIn(user)

    expect(await screen.findByText('Your coverage at a glance')).toBeInTheDocument()
    expect(screen.getByText('Welcome back, Maya')).toBeInTheDocument()
    expect(Object.keys(localStorage)).toEqual(['cc-auth'])
  })

  it('a wrong password shows the server message and stays on the log-in page', async () => {
    await existingAccount()
    const user = userEvent.setup()
    renderApp()
    await logIn(user, 'maya@example.com', 'not-the-password')
    expect(await screen.findByText("That email and password don't match. Try again, or reset your password.")).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toHaveValue('')
  })

  it('signing out clears the session; logging back in brings the answers back', async () => {
    await existingAccount()
    const user = userEvent.setup()
    renderApp()
    await logIn(user)
    await screen.findByText('Your coverage at a glance')
    const { token } = JSON.parse(localStorage.getItem('cc-auth')!)

    await user.click(screen.getByRole('button', { name: /Sign out/ }))
    expect(await screen.findByRole('button', { name: 'Create account' })).toBeInTheDocument()
    expect(localStorage.length).toBe(0)
    await waitFor(() => expect(server.tokens.has(token)).toBe(false))

    await logIn(user)
    expect(await screen.findByText('Your coverage at a glance')).toBeInTheDocument()
  })

  it('forgot password: emails a link, and the link sets a new password and signs in', async () => {
    await existingAccount()
    const user = userEvent.setup()
    const { unmount } = renderApp('/auth')
    await user.click(within(await screen.findByRole('group', { name: 'Sign up or log in' })).getByRole('button', { name: 'Log in' }))
    await user.click(screen.getByRole('button', { name: 'Forgot password?' }))
    await user.type(screen.getByLabelText('Email'), 'MAYA@example.com')
    await user.click(screen.getByRole('button', { name: 'Email me a reset link' }))
    expect(await screen.findByText(/we've sent it a link to choose a new password/)).toBeInTheDocument()
    const [{ token }] = server.sentResets
    unmount()

    renderApp(`/reset-password#token=${token}`)
    await user.type(await screen.findByLabelText('New password'), 'a fresh passphrase')
    await user.type(screen.getByLabelText('Type it again'), 'a fresh passphrase')
    await user.click(screen.getByRole('button', { name: 'Save new password' }))
    expect(await screen.findByText('Your coverage at a glance')).toBeInTheDocument()
  })

  it('a reset link without a valid token explains what to do', async () => {
    renderApp('/reset-password#token=nope')
    expect(await screen.findByText(/This reset link is incomplete/)).toBeInTheDocument()
  })

  it('reset: the two passwords must match', async () => {
    const user = userEvent.setup()
    renderApp(`/reset-password#token=${'b'.repeat(64)}`)
    await user.type(await screen.findByLabelText('New password'), 'a fresh passphrase')
    await user.type(screen.getByLabelText('Type it again'), 'a different one')
    await user.click(screen.getByRole('button', { name: 'Save new password' }))
    expect(screen.getByText("The two passwords don't match.")).toBeInTheDocument()
  })

  it('changes the password from My info', async () => {
    await existingAccount()
    const user = userEvent.setup()
    renderApp()
    await logIn(user)
    await user.click(await screen.findByRole('link', { name: 'My info' }))
    await user.type(await screen.findByLabelText('Current password'), 'long-enough')
    await user.type(screen.getByLabelText('New password'), 'an even better one')
    await user.click(screen.getByRole('button', { name: 'Change password' }))
    expect(await screen.findByText('Password changed. Any other devices were signed out.')).toBeInTheDocument()
    expect(server.users.get([...server.users.keys()][0])?.password).toBe('an even better one')
  })

  it('a sign-in the server no longer accepts returns to log in with a notice', async () => {
    localStorage.setItem(
      'cc-auth',
      JSON.stringify({ token: 'f'.repeat(64), expiresAt: new Date(Date.now() + 3600_000).toISOString(), account: { name: 'Maya', email: 'maya@example.com', hasPassword: true } }),
    )
    renderApp()
    expect(await screen.findByText('Your sign-in has expired. Please log in again.')).toBeInTheDocument()
    expect(localStorage.getItem('cc-auth')).toBeNull()
  })

  it('offers to try again when saved answers fail to load', async () => {
    await existingAccount()
    const user = userEvent.setup()
    renderApp()
    server.failProfile(500)
    await logIn(user)
    expect(await screen.findByText("We couldn't load your saved answers")).toBeInTheDocument()
    server.failProfile(null)
    await user.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByText('Your coverage at a glance')).toBeInTheDocument()
  })

  it('says so when a change could not be saved', async () => {
    await existingAccount()
    const user = userEvent.setup()
    renderApp()
    await logIn(user)
    await user.click(await screen.findByRole('link', { name: 'My info' }))
    server.failProfile(0)
    const income = await screen.findByLabelText('Yearly income')
    await user.clear(income)
    await user.type(income, '90,000')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))
    expect(await screen.findByText(/Your latest changes haven't been saved to your account yet/)).toBeInTheDocument()
  })
})
