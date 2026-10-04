import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import App from '../App'
import { AppProvider } from '../state/AppContext'

const renderExample = async () => {
  vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 404 })))
  const user = userEvent.setup()
  render(
    <MemoryRouter initialEntries={['/auth']}>
      <AppProvider>
        <App />
      </AppProvider>
    </MemoryRouter>,
  )
  await user.click(await screen.findByRole('button', { name: 'Explore with example data instead' }))
  return user
}

describe('Explanations', () => {
  it('explains a dashboard number on keyboard focus and hides it with Escape', async () => {
    const user = await renderExample()
    const info = screen.getByRole('button', { name: 'How we got coverage in place' })
    const tip = document.getElementById(info.getAttribute('aria-describedby')!)!
    expect(tip).not.toBeVisible()

    act(() => info.focus())
    expect(tip).toBeVisible()
    expect(tip).toHaveTextContent('$156,000 through work + $0 in policies you own + $20,000 in savings you counted = $176,000.')
    await user.keyboard('{Escape}')
    expect(tip).not.toBeVisible()
  })

  it('defines an insurance term on hover, and on tap', async () => {
    const user = await renderExample()
    await user.click(screen.getByRole('link', { name: 'Breakdown' }))
    const term = screen.getAllByRole('button', { name: 'Term life' })[0]
    const tip = document.getElementById(term.getAttribute('aria-describedby')!)!

    fireEvent.mouseEnter(term)
    expect(tip).toBeVisible()
    expect(tip).toHaveTextContent('Coverage for a set number of years, such as 20 or 30.')
    fireEvent.mouseLeave(term)
    expect(tip).not.toBeVisible()

    await user.click(term)
    expect(tip).toBeVisible()
  })

  it('explains the Breakdown starting point and range', async () => {
    const user = await renderExample()
    await user.click(screen.getByRole('link', { name: 'Breakdown' }))
    const start = screen.getByRole('button', { name: 'How we got the starting point' })
    act(() => start.focus())
    expect(document.getElementById(start.getAttribute('aria-describedby')!)).toHaveTextContent('starting point of $1,425,000')
    const range = screen.getByRole('button', { name: 'How we got the range' })
    act(() => range.focus())
    expect(document.getElementById(range.getAttribute('aria-describedby')!)).toHaveTextContent('About 15% below and above the $1,408,500')
  })
})
