import { useEffect, useId, useRef, useState } from 'react'
import { DEFAULT_PREFERENCES, applyPreferences, loadPreferences, savePreferences, type Preferences, type TextSize } from '../services/preferences'

const SIZES: [TextSize, string][] = [
  ['default', 'Default'],
  ['large', 'Large'],
  ['larger', 'Larger'],
]

/* Top-bar menu for display settings: text size, high contrast and an easier-to-read font. */
export function AccessibilityMenu() {
  const [open, setOpen] = useState(false)
  const [prefs, setPrefs] = useState<Preferences>(loadPreferences)
  const panelId = useId()
  const wrap = useRef<HTMLDivElement>(null)
  const button = useRef<HTMLButtonElement>(null)

  const update = (patch: Partial<Preferences>) => {
    const next = { ...prefs, ...patch }
    setPrefs(next)
    savePreferences(next)
    applyPreferences(next)
  }

  // Close on Escape (returning focus to the button) or on a click outside the menu.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      setOpen(false)
      button.current?.focus()
    }
    const onClick = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('mousedown', onClick)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', onClick)
    }
  }, [open])

  return (
    <div className="a11y" ref={wrap}>
      <button
        ref={button}
        type="button"
        className="a11y-btn"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((o) => !o)}
      >
        <span aria-hidden>Aa</span>
        <span className="a11y-label">Display settings</span>
      </button>
      {open && (
        <div id={panelId} className="a11y-panel card" role="group" aria-label="Display settings">
          <fieldset>
            <legend>Text size</legend>
            <div className="a11y-sizes">
              {SIZES.map(([value, label]) => (
                <label key={value}>
                  <input type="radio" name={`${panelId}-size`} checked={prefs.textSize === value} onChange={() => update({ textSize: value })} />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="a11y-toggle">
            <input type="checkbox" checked={prefs.highContrast} onChange={(e) => update({ highContrast: e.target.checked })} />
            <span>
              High contrast
              <span className="muted small">Darker text and stronger borders</span>
            </span>
          </label>
          <label className="a11y-toggle">
            <input type="checkbox" checked={prefs.readableFont} onChange={(e) => update({ readableFont: e.target.checked })} />
            <span>
              Easier-to-read font
              <span className="muted small">Plainer letters with more spacing</span>
            </span>
          </label>
          <button type="button" className="linkish small" onClick={() => update(DEFAULT_PREFERENCES)}>
            Reset to default
          </button>
        </div>
      )}
    </div>
  )
}
