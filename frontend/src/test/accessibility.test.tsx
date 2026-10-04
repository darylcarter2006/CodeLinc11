import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'
import App from '../App'
import { DEFAULT_PREFERENCES, applyPreferences } from '../services/preferences'
import { AppProvider } from '../state/AppContext'

const root = document.documentElement

afterEach(() => {
  applyPreferences(DEFAULT_PREFERENCES)
  document.querySelectorAll('link[data-readable-font]').forEach((l) => l.remove())
})

const renderApp = () =>
  render(
    <MemoryRouter initialEntries={['/auth']}>
      <AppProvider>
        <App />
      </AppProvider>
    </MemoryRouter>,
  )

describe('Display settings menu', () => {
  it('changes text size, contrast and font, and remembers them', async () => {
    const user = userEvent.setup()
    const { unmount } = renderApp()

    const toggle = screen.getByRole('button', { name: /Display settings/ })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')

    await user.click(screen.getByRole('radio', { name: 'Larger' }))
    await user.click(screen.getByRole('checkbox', { name: /High contrast/ }))
    await user.click(screen.getByRole('checkbox', { name: /Easier-to-read font/ }))
    expect(root.dataset).toMatchObject({ text: 'larger', contrast: 'high', font: 'readable' })
    expect(JSON.parse(localStorage.getItem('cc-preferences')!)).toEqual({ textSize: 'larger', highContrast: true, readableFont: true })

    // A fresh visit shows the saved choices.
    unmount()
    renderApp()
    await user.click(screen.getByRole('button', { name: /Display settings/ }))
    expect(screen.getByRole('radio', { name: 'Larger' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: /High contrast/ })).toBeChecked()

    await user.click(screen.getByRole('button', { name: 'Reset to default' }))
    expect(root.hasAttribute('data-text')).toBe(false)
    expect(screen.getByRole('radio', { name: 'Default' })).toBeChecked()
  })

  it('closes with Escape and returns focus to the button', async () => {
    const user = userEvent.setup()
    renderApp()
    const toggle = screen.getByRole('button', { name: /Display settings/ })
    await user.click(toggle)
    expect(screen.getByRole('group', { name: 'Display settings' })).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('group', { name: 'Display settings' })).not.toBeInTheDocument()
    expect(toggle).toHaveFocus()
  })
})
