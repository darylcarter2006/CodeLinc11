import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { short } from '../domain/format'
import { compute } from '../domain/needs'
import { EXAMPLE } from '../domain/profile'
import { AppProvider } from '../state/AppContext'

// No AI endpoints in tests: every call gets a 404, so onboarding uses only the local parser.
beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 404 })))
})

const renderApp = () =>
  render(
    <MemoryRouter initialEntries={['/']}>
      <AppProvider>
        <App />
      </AppProvider>
    </MemoryRouter>,
  )

const tile = (tone: string) => within(screen.getByTestId(`tile-${tone}`))

const expectTiles = (p = EXAMPLE) => {
  const c = compute(p)
  expect(tile('have').getByText(short(c.existing))).toBeInTheDocument()
  expect(tile('need').getByText(short(c.total))).toBeInTheDocument()
  expect(tile('left').getByText(short(c.gap))).toBeInTheDocument()
  expect(tile('term').getByText(`${c.term} yrs`)).toBeInTheDocument()
}

describe('full flow', () => {
  it('sign up → onboarding (local parser) → dashboard → edit income → tiles and log update', async () => {
    const user = userEvent.setup()
    renderApp()

    await user.type(await screen.findByLabelText('First name'), 'Maya')
    await user.type(screen.getByLabelText('Email'), 'maya@example.com')
    await user.type(screen.getByLabelText('Password'), 'long-enough')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByText(/Hi Maya!/)).toBeInTheDocument()
    const answers = ['Partner and kids', '2', '3', '34', '$78k', 'Until my youngest is 22', '$240,000', '26', '18000', 'Yes, public in-state', '2x salary', 'None', '$20k']
    const input = screen.getByLabelText('Your answer')
    for (const answer of answers) {
      await waitFor(() => expect(input).toBeEnabled())
      await user.type(input, `${answer}{Enter}`)
    }

    await user.click(await screen.findByRole('button', { name: 'Looks right, show my dashboard' }))
    expect(await screen.findByText('Your coverage at a glance')).toBeInTheDocument()
    expectTiles()

    await user.click(screen.getByRole('link', { name: 'My info' }))
    const income = await screen.findByLabelText('Yearly income')
    await user.clear(income)
    await user.type(income, '95,000')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))
    expect(await screen.findByText('Saved 1 change. Your dashboard and breakdown are updated.')).toBeInTheDocument()
    expect(screen.getByText('Yearly income: $78,000 → $95,000')).toBeInTheDocument()
    expect(screen.getByText('Created your profile in the onboarding chat')).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: 'Dashboard' }))
    expectTiles({ ...EXAMPLE, income: 95000 })
    // Types all 13 onboarding answers, so it needs more than the 5s default on slower machines.
  }, 20_000)

  it('example mode: breakdown "Why?" opens Chat with a standard answer', async () => {
    const user = userEvent.setup()
    renderApp()

    await user.click(await screen.findByRole('button', { name: 'Explore with example data instead' }))
    expect(await screen.findByText(/You're viewing an example/)).toBeInTheDocument()
    expectTiles()

    await user.click(screen.getByRole('link', { name: 'Breakdown' }))
    expect(screen.getByTestId('suggested')).toHaveTextContent('$1,425,000')
    await user.click(screen.getAllByRole('button', { name: 'Why?' })[0])

    expect(await screen.findByText(/Replacing about 75%/)).toBeInTheDocument()
    expect(screen.getByText("Standard answer. Live answers aren't available in this view.")).toBeInTheDocument()
  })

  it('shows one inline error at a time on sign up', async () => {
    const user = userEvent.setup()
    renderApp()
    await user.click(await screen.findByRole('button', { name: 'Create account' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Enter your first name.')
  })
})
