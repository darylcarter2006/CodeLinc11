import { useState, type FormEvent } from 'react'
import type { ProfileFieldName } from '../api/types'
import { ExpenseEditor } from '../components/ExpenseEditor'
import { useSession } from '../session/context'
import { FIELD_LABELS, MONEY_FIELDS, formatFieldValue, parseWholeDollars } from '../utils/format'

const SECTIONS: { title: string; fields: ProfileFieldName[] }[] = [
  { title: 'Dependents', fields: ['dependents_count', 'youngest_dependent_age'] },
  { title: 'Income and support', fields: ['annual_support_need', 'annual_survivor_contribution', 'support_years'] },
  { title: 'Debts and one-time costs', fields: ['one_time_expenses'] },
  { title: 'Existing coverage and assets', fields: ['personal_coverage', 'employer_coverage', 'available_assets'] },
  { title: 'Preferences', fields: ['budget_monthly'] },
]

/** Review and directly edit every answer. Edits are saved as confirmed. */
export function ProfilePage() {
  const { state, busy, updateProfile } = useSession()
  const [editing, setEditing] = useState<ProfileFieldName | null>(null)

  if (!state) return <p className="muted">Loading…</p>
  const { profile } = state

  const unconfirmed = (Object.keys(FIELD_LABELS) as ProfileFieldName[]).filter(
    (name) => profile[name] !== null && !profile[name]!.confirmed,
  )

  return (
    <div className="profile-page">
      <h1>My answers</h1>
      <p className="muted">
        Values from the chat are marked "from chat" until you confirm them. Editing a value here confirms it.
      </p>
      {unconfirmed.length > 0 && (
        <div className="callout">
          {unconfirmed.length} answer{unconfirmed.length === 1 ? '' : 's'} not yet confirmed.{' '}
          <button type="button" disabled={busy} onClick={() => updateProfile({}, unconfirmed)}>
            Confirm all
          </button>
        </div>
      )}

      {SECTIONS.map((section) => (
        <section key={section.title} className="panel">
          <h2>{section.title}</h2>
          {section.fields.map((name) => {
            const field = profile[name]
            return (
              <div key={name} className="profile-row">
                <div>
                  <div>{FIELD_LABELS[name]}</div>
                  {field && (
                    <span className={`tag ${field.confirmed ? 'tag-ok' : 'tag-pending'}`}>
                      {field.confirmed ? 'Confirmed' : field.source === 'stated' ? 'From chat' : field.source}
                    </span>
                  )}
                </div>
                {editing === name ? (
                  name === 'one_time_expenses' ? (
                    <ExpenseEditor
                      initial={profile.one_time_expenses?.value ?? []}
                      disabled={busy}
                      onSave={(items) => updateProfile({ one_time_expenses: items }).then(() => setEditing(null))}
                    />
                  ) : (
                    <NumberEditor
                      name={name}
                      initial={field?.value as number | null | undefined}
                      onDone={() => setEditing(null)}
                    />
                  )
                ) : (
                  <div className="profile-value">
                    <strong>{formatFieldValue(name, field)}</strong>
                    <button type="button" className="link-button" onClick={() => setEditing(name)}>
                      Edit
                    </button>
                  </div>
                )}
              </div>
            )
          })}
        </section>
      ))}
    </div>
  )
}

function NumberEditor({
  name,
  initial,
  onDone,
}: {
  name: ProfileFieldName
  initial: number | null | undefined
  onDone: () => void
}) {
  const { busy, updateProfile } = useSession()
  const [raw, setRaw] = useState(initial == null ? '' : String(initial))
  const value = parseWholeDollars(raw)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (value === null) return
    await updateProfile({ [name]: value })
    onDone()
  }

  return (
    <form className="inline-editor" onSubmit={onSubmit}>
      <div className="input-with-prefix">
        {MONEY_FIELDS.has(name) && <span aria-hidden>$</span>}
        <input aria-label={FIELD_LABELS[name]} inputMode="numeric" value={raw} autoFocus onChange={(e) => setRaw(e.target.value)} />
      </div>
      <button type="submit" disabled={busy || value === null}>
        Save
      </button>
      <button
        type="button"
        className="secondary"
        disabled={busy}
        onClick={async () => {
          await updateProfile({ [name]: null })
          onDone()
        }}
      >
        Don't know
      </button>
      <button type="button" className="link-button" onClick={onDone}>
        Cancel
      </button>
    </form>
  )
}
