import { useEffect, useId, useRef, useState, type FormEvent } from 'react'
import { fmt } from '../domain/format'
import { trapTab } from './dialog'
import { httpSupport, type BestTime, type CallbackRequest, type ContactMethod, type SupportService } from '../services/support'

type Summary = NonNullable<CallbackRequest['summary']>

interface Props {
  onClose: () => void
  defaultName: string
  defaultEmail: string
  summary: Summary
  service?: SupportService
}

const TIMES: [BestTime, string][] = [
  ['any', 'Any time'],
  ['morning', 'Morning'],
  ['afternoon', 'Afternoon'],
  ['evening', 'Evening'],
]
const TOPIC_MAX = 1000

type Stage = 'form' | 'sending' | 'sent' | 'unavailable'

/* "Talk to a licensed Lincoln Financial representative": a callback request form. A person follows up; nothing here is a live agent. */
export function CallbackDialog({ onClose, defaultName, defaultEmail, summary, service = httpSupport }: Props) {
  const titleId = useId()
  const [name, setName] = useState(defaultName)
  const [method, setMethod] = useState<ContactMethod>('email')
  const [contact, setContact] = useState(defaultEmail)
  const [bestTime, setBestTime] = useState<BestTime>('any')
  const [topic, setTopic] = useState('')
  const [share, setShare] = useState(false)
  const [error, setError] = useState('')
  const [stage, setStage] = useState<Stage>('form')
  const firstField = useRef<HTMLInputElement>(null)
  const doneButton = useRef<HTMLButtonElement>(null)
  const close = useRef(onClose)
  useEffect(() => {
    close.current = onClose
  }, [onClose])

  // The submit button disappears when a result message replaces the form; keep focus in the dialog.
  useEffect(() => {
    if (stage === 'sent' || stage === 'unavailable') doneButton.current?.focus()
  }, [stage])

  // Once on open: focus the first field, close on Escape, and return focus to the opener afterwards.
  useEffect(() => {
    const opener = document.activeElement
    firstField.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && close.current()
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      if (opener instanceof HTMLElement) opener.focus()
    }
  }, [])

  const switchMethod = (m: ContactMethod) => {
    setMethod(m)
    setContact(m === 'email' ? defaultEmail : '')
    setError('')
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    const n = name.trim()
    const c = contact.trim()
    const t = topic.trim()
    if (!n) return setError('Enter your name.')
    if (method === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(c)) return setError('Enter a valid email address, like you@example.com.')
    const digits = c.replace(/\D/g, '')
    if (method === 'phone' && (digits.length < 10 || digits.length > 15)) return setError('Enter a phone number with area code, like (555) 123-4567.')
    if (!t) return setError('Tell us briefly what you would like help with.')
    setError('')
    setStage('sending')
    const result = await service.requestCallback({
      name: n,
      contactMethod: method,
      contact: method === 'email' ? c.toLowerCase() : c,
      bestTime,
      topic: t.slice(0, TOPIC_MAX),
      ...(share ? { summary } : {}),
    })
    if (result.ok) return setStage('sent')
    if (result.reason === 'unavailable') return setStage('unavailable')
    setStage('form')
    setError(
      result.reason === 'invalid'
        ? 'Something in the form was not accepted. Check your details and try again.'
        : "We couldn't send your request. Try again in a minute.",
    )
  }

  const timeText = bestTime === 'any' ? '' : `, in the ${bestTime}`

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal card" role="dialog" aria-modal="true" aria-labelledby={titleId} onKeyDown={trapTab}>
        <div className="modal-head">
          <div>
            <div className="eyebrow">Prefer a person?</div>
            <h2 id={titleId}>Talk to a licensed Lincoln Financial representative</h2>
          </div>
          <button className="linkish" type="button" onClick={onClose}>
            Close
          </button>
        </div>

        {stage === 'sent' && (
          <div className="stack" role="status">
            <p className="flush">
              <strong>Request sent.</strong> Thanks, {name.trim()}. A licensed Lincoln Financial representative will reach out by {method}{' '}
              at <b>{contact.trim()}</b>
              {timeText}.
            </p>
            <p className="muted small flush">You can keep asking the assistant questions in the meantime.</p>
            <div className="actions">
              <button className="btn" type="button" ref={doneButton} onClick={onClose}>
                Back to chat
              </button>
            </div>
          </div>
        )}

        {stage === 'unavailable' && (
          <div className="stack" role="status">
            <p className="flush">
              <strong>Callback requests aren't connected yet</strong>, so nothing was sent. You can keep asking questions
              here, or try again later.
            </p>
            <div className="actions">
              <button className="btn" type="button" ref={doneButton} onClick={onClose}>
                Back to chat
              </button>
            </div>
          </div>
        )}

        {(stage === 'form' || stage === 'sending') && (
          <form className="stack" onSubmit={submit} noValidate>
            <p className="muted small flush">
              If the assistant isn't answering what you need, ask for a licensed Lincoln Financial representative to follow up with you.
            </p>
            <div className="field">
              <label htmlFor="cb-name">Your name</label>
              <div className="in">
                <input id="cb-name" ref={firstField} autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
            </div>
            <fieldset className="field">
              <legend>How should we reach you?</legend>
              <div className="checks">
                {(['email', 'phone'] as ContactMethod[]).map((m) => (
                  <label key={m}>
                    <input type="radio" name="cb-method" checked={method === m} onChange={() => switchMethod(m)} />
                    {m === 'email' ? 'Email' : 'Phone'}
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="fields">
              <div className="field">
                <label htmlFor="cb-contact">{method === 'email' ? 'Email address' : 'Phone number'}</label>
                <div className="in">
                  <input
                    id="cb-contact"
                    type={method === 'email' ? 'email' : 'tel'}
                    autoComplete={method === 'email' ? 'email' : 'tel'}
                    value={contact}
                    onChange={(e) => setContact(e.target.value)}
                  />
                </div>
              </div>
              <div className="field">
                <label htmlFor="cb-time">Best time</label>
                <div className="in">
                  <select id="cb-time" value={bestTime} onChange={(e) => setBestTime(e.target.value as BestTime)}>
                    {TIMES.map(([v, l]) => (
                      <option key={v} value={v}>
                        {l}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
            <div className="field">
              <label htmlFor="cb-topic">What would you like help with?</label>
              <div className="in">
                <textarea
                  id="cb-topic"
                  rows={3}
                  maxLength={TOPIC_MAX}
                  value={topic}
                  placeholder="For example: I'm not sure whether to count my work coverage."
                  onChange={(e) => setTopic(e.target.value)}
                />
              </div>
              <div className="muted small count">
                {topic.length} / {TOPIC_MAX}
              </div>
            </div>
            <label className="share">
              <input type="checkbox" checked={share} onChange={(e) => setShare(e.target.checked)} />
              <span>Share my estimate and recent questions so they can prepare</span>
            </label>
            {share && (
              <ul className="share-preview small">
                <li>
                  Estimated need {fmt(summary.estimate.total)}, in place {fmt(summary.estimate.existing)}, left to cover{' '}
                  {fmt(summary.estimate.gap)}, suggested term {summary.estimate.termYears} years
                </li>
                {summary.recentQuestions.length ? (
                  summary.recentQuestions.map((q, i) => <li key={i}>“{q}”</li>)
                ) : (
                  <li>No questions asked yet</li>
                )}
              </ul>
            )}
            <p className="fine flush">
              Please don't include Social Security numbers, account numbers or medical details. This is an educational
              tool, not a quote.
            </p>
            {error && (
              <div className="err" role="alert">
                {error}
              </div>
            )}
            <div className="actions">
              <button className="btn" type="submit" disabled={stage === 'sending'}>
                {stage === 'sending' ? 'Sending…' : 'Request a callback'}
              </button>
              <button className="btn ghost" type="button" onClick={onClose}>
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
