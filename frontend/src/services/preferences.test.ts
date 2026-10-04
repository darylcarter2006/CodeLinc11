import { afterEach, describe, expect, it } from 'vitest'
import { DEFAULT_PREFERENCES, applyPreferences, loadPreferences, savePreferences } from './preferences'

const root = document.documentElement

afterEach(() => {
  applyPreferences(DEFAULT_PREFERENCES)
  document.querySelectorAll('link[data-readable-font]').forEach((l) => l.remove())
})

describe('display preferences', () => {
  it('defaults when nothing is saved or the saved value is bad', () => {
    expect(loadPreferences()).toEqual(DEFAULT_PREFERENCES)
    localStorage.setItem('cc-preferences', JSON.stringify({ textSize: 'huge', highContrast: 'yes' }))
    expect(loadPreferences()).toEqual(DEFAULT_PREFERENCES)
  })

  it('saves and loads', () => {
    savePreferences({ textSize: 'larger', highContrast: true, readableFont: false })
    expect(loadPreferences()).toEqual({ textSize: 'larger', highContrast: true, readableFont: false })
  })

  it('applies settings as attributes on <html> and loads the readable font once', () => {
    applyPreferences({ textSize: 'large', highContrast: true, readableFont: true })
    applyPreferences({ textSize: 'large', highContrast: true, readableFont: true })
    expect(root.dataset).toMatchObject({ text: 'large', contrast: 'high', font: 'readable' })
    expect(document.querySelectorAll('link[data-readable-font]')).toHaveLength(1)

    applyPreferences(DEFAULT_PREFERENCES)
    expect(root.hasAttribute('data-text') || root.hasAttribute('data-contrast') || root.hasAttribute('data-font')).toBe(false)
  })
})
