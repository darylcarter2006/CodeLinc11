import { useEffect, useId, useRef } from 'react'
import { POLICY_TYPE, type PolicyFit } from '../domain/policy'
import { trapTab } from './dialog'

interface Props {
  fit: PolicyFit
  onClose: () => void
  onTalkToRep: () => void
}

/* The coverage-type result: which type fits their answers, why, and a way to talk to a person. */
export function PolicyResultDialog({ fit, onClose, onTalkToRep }: Props) {
  const titleId = useId()
  const type = POLICY_TYPE[fit.type]
  const closeButton = useRef<HTMLButtonElement>(null)
  const close = useRef(onClose)
  useEffect(() => {
    close.current = onClose
  }, [onClose])

  // Once on open: focus the main button, close on Escape, and return focus to the opener afterwards.
  useEffect(() => {
    const opener = document.activeElement
    closeButton.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && close.current()
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      if (opener instanceof HTMLElement) opener.focus()
    }
  }, [])

  const ordered = [...fit.reasons.filter((r) => r.side === fit.type), ...fit.reasons.filter((r) => r.side !== fit.type)]

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal card policy-result" role="dialog" aria-modal="true" aria-labelledby={titleId} onKeyDown={trapTab}>
        <div className="modal-head">
          <div>
            <div className="eyebrow">Your coverage type</div>
            <h2 id={titleId}>{type.name} fits best</h2>
          </div>
        </div>

        <p className="flush">{type.summary}</p>
        <ul className="policy-points">
          {type.points.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>

        <h3>Why, based on your answers</h3>
        <ul className="policy-reasons">
          {ordered.map((r) => (
            <li key={r.field}>
              <span className={`pill ${r.side === fit.type ? 'ok' : ''}`}>{r.side === 'term' ? 'Term' : 'Permanent'}</span>
              <span>{r.text}</span>
            </li>
          ))}
        </ul>
        <p className="muted small flush">
          {fit.term} of your answers point to term and {fit.perm} to permanent. This is educational guidance from your answers, not a quote
          or a recommendation of a specific product. You can change your answers any time in My info.
        </p>

        <div className="actions">
          <button className="btn" type="button" ref={closeButton} onClick={onClose}>
            Go to my dashboard
          </button>
          <button className="btn ghost" type="button" onClick={onTalkToRep}>
            Talk to a licensed representative
          </button>
        </div>
      </div>
    </div>
  )
}
