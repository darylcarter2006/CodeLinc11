import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import type { NextQuestion, ProfileFieldName } from '../api/types'
import { useSession } from '../session/context'
import { fieldLabel, formatFieldValue, parseWholeDollars } from '../utils/format'
import { ExpenseEditor } from './ExpenseEditor'

/** Typed control for the server's `next_question`; answers go through PATCH /profile. */
export function QuestionInput({ question }: { question: NextQuestion }) {
  const { state, busy, updateProfile } = useSession()
  const [raw, setRaw] = useState('')
  const [invalid, setInvalid] = useState<string | null>(null)

  if (!state) return null

  if (question.input_type === 'confirm') {
    const fields = question.review_fields
    return (
      <div className="question-input">
        <ul className="review-list">
          {fields.map((name) => (
            <li key={name}>
              <span>{fieldLabel(name)}</span>
              <strong>{formatFieldValue(name, state.profile[name])}</strong>
            </li>
          ))}
        </ul>
        <div className="button-row">
          <button type="button" disabled={busy} onClick={() => updateProfile({}, fields)}>
            These look right
          </button>
          <Link to="/profile" className="button secondary">
            Edit answers
          </Link>
        </div>
      </div>
    )
  }

  const field = question.field as ProfileFieldName

  if (question.input_type === 'expenses') {
    const current = state.profile.one_time_expenses?.value ?? []
    return (
      <div className="question-input">
        <ExpenseEditor initial={current} disabled={busy} onSave={(items) => updateProfile({ one_time_expenses: items })} />
        {question.allow_unknown && (
          <button type="button" className="link-button" disabled={busy} onClick={() => updateProfile({ one_time_expenses: null })}>
            I don't know
          </button>
        )}
      </div>
    )
  }

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    const value = parseWholeDollars(raw)
    if (value === null) return setInvalid('Please enter a whole number.')
    if (question.min !== null && value < question.min) return setInvalid(`Must be at least ${question.min}.`)
    if (question.max !== null && value > question.max) return setInvalid(`Must be at most ${question.max.toLocaleString()}.`)
    setInvalid(null)
    setRaw('')
    void updateProfile({ [field]: value })
  }

  return (
    <form className="question-input" onSubmit={onSubmit}>
      <div className="input-with-prefix">
        {question.input_type === 'currency' && <span aria-hidden>$</span>}
        <input
          aria-label={fieldLabel(field)}
          inputMode="numeric"
          value={raw}
          disabled={busy}
          placeholder={question.input_type === 'currency' ? '80,000' : '0'}
          onChange={(e) => setRaw(e.target.value)}
        />
        <button type="submit" disabled={busy || raw.trim() === ''}>
          Save
        </button>
      </div>
      {invalid && <p className="error-text">{invalid}</p>}
      {question.allow_unknown && (
        <button type="button" className="link-button" disabled={busy} onClick={() => updateProfile({ [field]: null })}>
          I don't know
        </button>
      )}
    </form>
  )
}
