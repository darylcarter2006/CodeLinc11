import { storage } from './storage'

/*
 * Display preferences (accessibility settings). Saved in this browser only and applied as
 * data attributes on <html>, which index.css uses to resize text, raise contrast or swap fonts.
 */

export type TextSize = 'default' | 'large' | 'larger'

export interface Preferences {
  textSize: TextSize
  highContrast: boolean
  readableFont: boolean
}

export const DEFAULT_PREFERENCES: Preferences = { textSize: 'default', highContrast: false, readableFont: false }

const KEY = 'preferences'
const TEXT_SIZES: TextSize[] = ['default', 'large', 'larger']
// Atkinson Hyperlegible was designed for low-vision readers; only loaded when someone turns it on.
const READABLE_FONT_HREF = 'https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&display=swap'

export function loadPreferences(): Preferences {
  const saved = storage.get<Partial<Preferences>>(KEY) ?? {}
  return {
    textSize: TEXT_SIZES.includes(saved.textSize as TextSize) ? (saved.textSize as TextSize) : 'default',
    highContrast: saved.highContrast === true,
    readableFont: saved.readableFont === true,
  }
}

export function savePreferences(p: Preferences): void {
  storage.set(KEY, p)
}

export function applyPreferences(p: Preferences, root: HTMLElement = document.documentElement): void {
  const set = (name: string, value: string | null) => (value ? root.setAttribute(name, value) : root.removeAttribute(name))
  set('data-text', p.textSize === 'default' ? null : p.textSize)
  set('data-contrast', p.highContrast ? 'high' : null)
  set('data-font', p.readableFont ? 'readable' : null)
  if (p.readableFont && !document.querySelector('link[data-readable-font]')) {
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    link.href = READABLE_FONT_HREF
    link.dataset.readableFont = ''
    document.head.append(link)
  }
}
