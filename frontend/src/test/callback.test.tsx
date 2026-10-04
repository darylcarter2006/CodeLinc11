import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import App from '../App'
import { AppProvider } from '../state/AppContext'

// AI endpoints answer 404 (standard answers); the callback endpoint answers with `callbackStatus`.
const setup = (callbackStatus: number) => {
  const fetch = vi.fn(async (url: string) => new Response(null, { status: url.includes('/support/') ? callbackStatus : 404 }))
  vi.stubGlobal('fetch', fetch)
  render(
    <MemoryRouter initialEntries={['/auth']}>
      <AppProvider>
        <App />
      </AppProvider>
    </MemoryRouter>,
  )
  const callbackBody = () => {
    const call = fetch.mock.calls.find(([url]) => url.includes('/support/')) as unknown as [string, RequestInit] | undefined
    return call ? JSON.parse(String(call[1].body)) : null
  }
  return { user: userEvent.setup(), callbackBody }
}

const openDialog = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(await screen.findByRole('button', { name: 'Explore with example data instead' }))
  await user.click(await screen.findByRole('link', { name: 'Chat' }))
  await user.click(await screen.findByRole('button', { name: 'Term or whole life for me?' }))
  await user.click(screen.getByRole('button', { name: 'Talk to a licensed Lincoln Financial representative' }))
  return screen.getByRole('dialog', { name: 'Talk to a licensed Lincoln Financial representative' })
}

describe('Talk to a licensed Lincoln Financial representative', () => {
  it('validates one field at a time', async () => {
    const { user, callbackBody } = setup(201)
    await openDialog(user)
    expect(screen.getByLabelText('Your name')).toHaveFocus()

    await user.click(screen.getByRole('button', { name: 'Request a callback' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Enter your name.')
    await user.type(screen.getByLabelText('Your name'), 'Maya')
    await user.click(screen.getByRole('radio', { name: 'Phone' }))
    await user.type(screen.getByLabelText('Phone number'), '555-1234')
    await user.click(screen.getByRole('button', { name: 'Request a callback' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a phone number with area code')
    await user.type(screen.getByLabelText('Phone number'), '999')
    await user.click(screen.getByRole('button', { name: 'Request a callback' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Tell us briefly what you would like help with.')
    await user.type(screen.getByLabelText('What would you like help with?'), 'My SSN is 123-45-6789')
    await user.click(screen.getByRole('button', { name: 'Request a callback' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Please remove Social Security, account or card numbers.')
    expect(callbackBody()).toBeNull()
  })

  it('sends the request, with the summary only when shared', async () => {
    const { user, callbackBody } = setup(201)
    await openDialog(user)
    await user.type(screen.getByLabelText('Your name'), 'Maya')
    await user.type(screen.getByLabelText('Email address'), 'maya@example.com')
    await user.selectOptions(screen.getByLabelText('Best time'), 'morning')
    await user.type(screen.getByLabelText('What would you like help with?'), 'Should I count my work coverage?')
    await user.click(screen.getByRole('checkbox', { name: /Share my estimate/ }))
    expect(screen.getByText('“Term or whole life for me?”')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Request a callback' }))

    expect(await screen.findByText(/Request sent\./)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Done' })).toHaveFocus()
    expect(screen.getByRole('status')).toHaveTextContent('reach out by email at maya@example.com, in the morning.')
    expect(callbackBody()).toEqual({
      name: 'Maya',
      contactMethod: 'email',
      contact: 'maya@example.com',
      bestTime: 'morning',
      topic: 'Should I count my work coverage?',
      summary: {
        estimate: { total: 1584500, existing: 176000, gap: 1408500, suggested: 1425000, termYears: 30 },
        recentQuestions: ['Term or whole life for me?'],
      },
    })
  })

  it('says plainly when callback requests are not connected, and closes with Escape', async () => {
    const { user, callbackBody } = setup(404)
    await openDialog(user)
    await user.type(screen.getByLabelText('Your name'), 'Maya')
    await user.type(screen.getByLabelText('Email address'), 'maya@example.com')
    await user.type(screen.getByLabelText('What would you like help with?'), 'Help')
    await user.click(screen.getByRole('button', { name: 'Request a callback' }))

    expect(await screen.findByText(/aren't connected yet/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Done' })).toHaveFocus()
    expect(callbackBody()).not.toHaveProperty('summary')
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Talk to a licensed Lincoln Financial representative' })).toHaveFocus()
  })

  it('keeps keyboard focus inside the dialog', async () => {
    const { user } = setup(201)
    await openDialog(user)
    const close = screen.getByRole('button', { name: 'Close' })
    const cancel = screen.getByRole('button', { name: 'Cancel' })

    cancel.focus()
    await user.tab()
    expect(close).toHaveFocus()
    await user.tab({ shift: true })
    expect(cancel).toHaveFocus()
  })
})
