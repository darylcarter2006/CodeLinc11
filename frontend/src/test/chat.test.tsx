import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import App from '../App'
import { AppProvider } from '../state/AppContext'
import { installFakeServer } from './fakeServer'

const json = (body: unknown, status: number) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

async function askInExample(question: string) {
  const user = userEvent.setup()
  render(
    <MemoryRouter initialEntries={['/auth']}>
      <AppProvider>
        <App />
      </AppProvider>
    </MemoryRouter>,
  )
  await user.click(await screen.findByRole('button', { name: 'Explore with example data instead' }))
  await user.click(await screen.findByRole('link', { name: 'Chat' }))
  await user.click(await screen.findByRole('button', { name: question }))
}

describe('Chat answers from the model', () => {
  it('shows a checked answer from the server', async () => {
    installFakeServer({ chat: () => new Response('75% of $78,000 is $58,500 a year.', { status: 200, headers: { 'Content-Type': 'text/plain' } }) })
    await askInExample('Term or whole life for me?')
    expect(await screen.findByText('75% of $78,000 is $58,500 a year.')).toBeInTheDocument()
  })

  it('says so, and shows the standard answer, when the server rejected the answer for unchecked numbers', async () => {
    installFakeServer({ chat: () => json({ error: { code: 'ai_unverified', message: 'x', request_id: 'r' } }, 502) })
    await askInExample('Term or whole life for me?')
    expect(await screen.findByText("Standard answer. The live answer's numbers didn't match your estimate, so it wasn't shown.")).toBeInTheDocument()
  })
})
