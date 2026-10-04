import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import App from '../App'
import { AppProvider } from '../state/AppContext'

describe('Breakdown when existing coverage already covers the need', () => {
  it('says so instead of showing a starting-point figure', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 404 })))
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/auth']}>
        <AppProvider>
          <App />
        </AppProvider>
      </MemoryRouter>,
    )

    // Maya's example needs $1,584,500; $2,000,000 through work more than covers it.
    await user.click(await screen.findByRole('button', { name: 'Explore with example data instead' }))
    await user.click(await screen.findByRole('link', { name: 'My info' }))
    const work = await screen.findByLabelText('Coverage through work')
    await user.clear(work)
    await user.type(work, '2,000,000')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))
    expect(await screen.findByText(/Saved 1 change/)).toBeInTheDocument()

    await user.click(screen.getByRole('link', { name: 'Breakdown' }))
    expect(screen.getByText('Good news')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'What you have already covers this estimate' })).toBeInTheDocument()
    expect(screen.getByText(/Your existing coverage and savings \(\$2,020,000\) meet the estimated need of \$1,584,500\./)).toBeInTheDocument()
    expect(screen.queryByTestId('suggested')).not.toBeInTheDocument()
    expect(screen.queryByText(/A reasonable starting point/)).not.toBeInTheDocument()
  })
})
