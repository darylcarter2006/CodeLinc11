import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import App from '../App'
import { AppProvider } from '../state/AppContext'
import { installFakeServer } from './fakeServer'

beforeEach(() => {
  installFakeServer()
})

const renderAt = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <AppProvider>
        <App />
      </AppProvider>
    </MemoryRouter>,
  )

describe('privacy policy and terms', () => {
  it('opens the privacy policy without signing in, with the retention periods', async () => {
    renderAt('/privacy')
    expect(await screen.findByRole('heading', { name: 'Privacy policy' })).toBeInTheDocument()
    expect(screen.getByText('180 days after you last sign in')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'terms of service' })).toHaveAttribute('href', '/terms')
  })

  it('opens the terms without signing in', async () => {
    renderAt('/terms')
    expect(await screen.findByRole('heading', { name: 'Terms of service' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'An estimate, not advice or a quote' })).toBeInTheDocument()
  })

  it('links both from the footer and the sign-up form', async () => {
    renderAt('/auth')
    expect(await screen.findByRole('link', { name: 'Privacy policy' })).toHaveAttribute('href', '/privacy')
    expect(screen.getByRole('link', { name: 'Terms of service' })).toHaveAttribute('href', '/terms')
    expect(screen.getByText(/By creating an account, you agree to the/)).toBeInTheDocument()
  })
})
