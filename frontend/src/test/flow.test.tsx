import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import App from '../App'
import { short } from '../domain/format'
import { compute } from '../domain/needs'
import { EXAMPLE } from '../domain/profile'
import { AppProvider } from '../state/AppContext'
import { installFakeServer, type FakeServer } from './fakeServer'

// A fake backend for accounts and saved profiles. AI endpoints answer 404, so onboarding uses only the local parser.
let server: FakeServer
beforeEach(() => {
  server = installFakeServer()
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
    // Coverage-type questions: 2 points to permanent, 3 to term, so term fits best.
    answers.push('My whole life', 'Lowest monthly cost', 'yes', 'no', 'Keep it simple')
    const input = screen.getByLabelText('Your answer')
    for (const answer of answers) {
      await waitFor(() => expect(input).toBeEnabled())
      await user.type(input, `${answer}{Enter}`)
    }

    await user.click(await screen.findByRole('button', { name: 'Looks right, show my dashboard' }))
    expect(await screen.findByText('Your coverage at a glance')).toBeInTheDocument()

    // The result pop-up opens on the first visit, then closes back to the dashboard.
    const result = await screen.findByRole('dialog', { name: 'Term life insurance fits best' })
    expect(within(result).getByText('3 of your answers point to term and 2 to permanent', { exact: false })).toBeInTheDocument()
    expect(within(result).getByText('You want coverage that lasts your whole life.')).toBeInTheDocument()
    await user.click(within(result).getByRole('button', { name: 'Go to my dashboard' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByTestId('policy-card')).toHaveTextContent('Term life insurance fits your answers best')
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
    // Same coverage type as before, so the pop-up doesn't reopen.
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    // Changing preferences until permanent wins opens the pop-up again with the new result.
    await user.click(screen.getByRole('link', { name: 'My info' }))
    await user.selectOptions(await screen.findByLabelText('Leave money to heirs'), 'yes')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))
    expect(await screen.findByText('Leave money to heirs: No → Yes')).toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: 'Dashboard' }))
    expect(await screen.findByRole('dialog', { name: 'Permanent life insurance fits best' })).toBeInTheDocument()
  })

  it('an old browser-only profile moves into the account, and its unanswered coverage questions stay unanswered', async () => {
    const saved = {
      p: { ...EXAMPLE, coverFor: undefined, budget: undefined, cashValue: undefined, legacy: undefined, simple: undefined },
      known: ['deps', 'children', 'youngest', 'age', 'income', 'years', 'mortgage', 'mortgageYears', 'otherDebt', 'college', 'group', 'policies', 'savings'],
      confirmed: true,
      updated: Date.now(),
    }
    // What the earlier browser-only version left in localStorage.
    localStorage.setItem('cc-account', JSON.stringify({ name: 'Maya', email: 'maya@example.com' }))
    localStorage.setItem('cc-session', 'true')
    localStorage.setItem('cc-profile', JSON.stringify(saved))
    localStorage.setItem('cc-log', JSON.stringify([{ at: 1, text: 'Created your profile in the onboarding chat' }]))
    const user = userEvent.setup()
    renderApp()

    await user.type(await screen.findByLabelText('First name'), 'Maya')
    await user.type(screen.getByLabelText('Email'), 'Maya@example.com')
    await user.type(screen.getByLabelText('Password'), 'long-enough')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByText('Your coverage at a glance')).toBeInTheDocument()
    // Moved to the account, and nothing financial left behind in the browser.
    await waitFor(() => expect(server.stateOf('maya@example.com')).toMatchObject({ saved: { confirmed: true } }))
    for (const key of ['cc-account', 'cc-session', 'cc-profile', 'cc-log']) expect(localStorage.getItem(key)).toBeNull()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByTestId('policy-card')).toHaveTextContent('Answer five quick questions')

    // Saving an unrelated change doesn't turn the unanswered questions into answers.
    await user.click(within(screen.getByTestId('policy-card')).getByRole('link', { name: 'My info' }))
    expect(await screen.findByLabelText('Build cash value')).toHaveValue('')
    const income = screen.getByLabelText('Yearly income')
    await user.clear(income)
    await user.type(income, '80,000')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))
    await user.click(screen.getByRole('link', { name: 'Dashboard' }))
    expect(screen.getByTestId('policy-card')).toHaveTextContent('Answer five quick questions')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

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

  it('"Change something" at the end of onboarding opens My info', async () => {
    const user = userEvent.setup()
    renderApp()
    await user.type(await screen.findByLabelText('First name'), 'Sam')
    await user.type(screen.getByLabelText('Email'), 'sam@example.com')
    await user.type(screen.getByLabelText('Password'), 'long-enough')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    const answers = ['No one', '40', '$60k', 'None', 'None', 'None', 'None', 'None']
    answers.push('My whole life', 'Lowest monthly cost', 'no', 'no', 'Keep it simple')
    const input = await screen.findByLabelText('Your answer')
    while (!screen.queryByRole('button', { name: 'Change something' })) {
      await waitFor(() => expect(input).toBeEnabled())
      const answer = answers.shift()
      if (!answer) throw new Error('onboarding asked more questions than expected')
      await user.type(input, `${answer}{Enter}`)
    }

    await user.click(screen.getByRole('button', { name: 'Change something' }))
    expect(await screen.findByRole('heading', { name: 'What we know about you' })).toBeInTheDocument()
  })

  it('shows one inline error at a time on sign up', async () => {
    const user = userEvent.setup()
    renderApp()
    await user.click(await screen.findByRole('button', { name: 'Create account' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Enter your first name.')
  })
})
