import { useRef, useState, type FormEvent } from 'react'
import { fmt, shortDate } from '../domain/format'
import { ADULT_AGE, compute } from '../domain/needs'
import {
  COLLEGE_LABEL,
  INT_FIELDS,
  LABEL,
  MONEY_FIELDS,
  POLICY_CHOICES,
  POLICY_FIELDS,
  isInt,
  showVal,
  type College,
  type Dep,
  type Field,
  type NumberField,
  type PolicyField,
  type Profile,
} from '../domain/profile'
import { useApp } from '../state/context'

type Status = { text: string; tone: 'muted' | 'error' | 'ok' }

const NUMBER_FIELDS: NumberField[] = [...MONEY_FIELDS, ...INT_FIELDS]
const DEP_OPTIONS: [Dep, string][] = [
  ['partner', 'Partner or spouse'],
  ['kids', 'Children'],
  ['relative', 'A parent or relative'],
  ['none', 'No one right now'],
]

/* My info: edit anything the chat saved. Saving diffs against the stored profile and logs each change. */
export function MyInfoPage() {
  const { profile, isExample, log, saveInfo, saved } = useApp()
  // In example mode every answer is set; otherwise only the questions actually answered count.
  const known = isExample ? [...POLICY_FIELDS] : saved.known
  const [status, setStatus] = useState<Status>({
    text: isExample ? 'Example data: changes last until you leave the example.' : 'Changes update your dashboard right away.',
    tone: 'muted',
  })

  return (
    <>
      <div className="view-head">
        <div>
          <div className="eyebrow">My info</div>
          <h2>What we know about you</h2>
          <div className="muted small">Fix anything that was saved wrong, or update it when life changes.</div>
        </div>
      </div>
      {/* Re-mount the form when the saved profile changes so inputs show the stored values. */}
      <InfoForm
        key={JSON.stringify([profile, known])}
        profile={profile}
        known={known}
        status={status}
        setStatus={setStatus}
        onSave={saveInfo}
      />
      {!isExample && (
        <div className="card pad spaced-lg">
          <div className="sec-head">
            <h2>Recent changes</h2>
          </div>
          {log.length ? (
            <ul className="log">
              {log.slice(0, 10).map((l, i) => (
                <li key={`${l.at}-${i}`}>
                  <time>{shortDate(l.at)}</time>
                  {l.text}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted flush">No changes yet.</p>
          )}
        </div>
      )}
      {!isExample && <AccountSettings />}
    </>
  )
}

interface FormProps {
  profile: Profile
  known: readonly Field[]
  status: Status
  setStatus: (s: Status) => void
  onSave: (next: Profile, changes: string[], policyChosen: PolicyField[]) => void
}

function InfoForm({ profile: p, known, status, setStatus, onSave }: FormProps) {
  const [deps, setDeps] = useState<Dep[]>(p.deps)
  const [college, setCollege] = useState<College>(p.college)
  // '' means not answered yet: shown as "Choose…" rather than a default that would skew the result.
  const [prefs, setPrefs] = useState(
    () => Object.fromEntries(POLICY_FIELDS.map((k) => [k, known.includes(k) ? p[k] : ''])) as Record<PolicyField, string>,
  )
  const [nums, setNums] = useState(() =>
    Object.fromEntries(NUMBER_FIELDS.map((k) => [k, Number(p[k] || 0).toLocaleString('en-US')])) as Record<NumberField, string>,
  )
  const [invalid, setInvalid] = useState<NumberField | null>(null)
  const inputs = useRef<Partial<Record<NumberField, HTMLInputElement | null>>>({})

  const toggleDep = (d: Dep, checked: boolean) => {
    if (!checked) return setDeps(deps.filter((x) => x !== d))
    setDeps(d === 'none' ? ['none'] : [...deps.filter((x) => x !== 'none'), d])
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const error = (text: string) => setStatus({ text, tone: 'error' })
    if (!deps.length) return error('Choose who relies on your income, or “No one right now”.')
    const ordered = DEP_OPTIONS.map(([d]) => d).filter((d) => deps.includes(d))
    const next: Profile = { ...p, deps: ordered, college }
    const chosen = POLICY_FIELDS.filter((k) => prefs[k] !== '')
    for (const k of chosen) (next as Record<PolicyField, string>)[k] = prefs[k]
    for (const k of NUMBER_FIELDS) {
      const raw = nums[k].replace(/[$,\s]/g, '')
      const n = Number(raw)
      if (raw === '' || !isFinite(n) || n < 0) {
        setInvalid(k)
        inputs.current[k]?.focus()
        return error(`Enter a number for “${LABEL[k]}” (0 is fine).`)
      }
      next[k] = isInt(k) ? Math.round(n) : n
    }
    setInvalid(null)
    if (ordered.includes('kids') && next.children < 1) {
      setInvalid('children')
      return error('Enter how many children, or uncheck Children.')
    }
    const newlyAnswered = chosen.filter((k) => !known.includes(k))
    const changed = ([...NUMBER_FIELDS, 'deps', 'college', ...POLICY_FIELDS] as Field[]).filter(
      (k) => JSON.stringify(next[k]) !== JSON.stringify(p[k]) || newlyAnswered.includes(k as PolicyField),
    )
    if (!changed.length) return setStatus({ text: 'Nothing changed.', tone: 'error' })
    const moved = movement(compute(p).suggested, compute(next).suggested)
    setStatus({
      text: `Saved ${changed.length} change${changed.length > 1 ? 's' : ''}. ${moved.sentence}`,
      tone: 'ok',
    })
    onSave(
      next,
      [
        ...changed.map((k) =>
          newlyAnswered.includes(k as PolicyField) ? `${LABEL[k]}: ${showVal(k, next)}` : `${LABEL[k]}: ${showVal(k, p)} → ${showVal(k, next)}`,
        ),
        ...(moved.log ? [moved.log] : []),
      ],
      chosen,
    )
  }

  const num = (k: NumberField, pre = '', suf = '') => (
    <div className="field">
      <label htmlFor={`i_${k}`}>{LABEL[k]}</label>
      <div className="in">
        {pre && <span className="aff">{pre}</span>}
        <input
          id={`i_${k}`}
          inputMode="numeric"
          value={nums[k]}
          aria-invalid={invalid === k || undefined}
          ref={(el) => {
            inputs.current[k] = el
          }}
          onChange={(e) => setNums({ ...nums, [k]: e.target.value })}
        />
        {suf && <span className="aff">{suf}</span>}
      </div>
    </div>
  )

  return (
    <form onSubmit={submit} noValidate>
      <div className="info-grid">
        <div className="card pad">
          <h3>Household</h3>
          <div className="stack">
            <fieldset className="field">
              <legend>Who relies on your income</legend>
              <div className="checks">
                {DEP_OPTIONS.map(([d, label]) => (
                  <label key={d}>
                    <input type="checkbox" checked={deps.includes(d)} onChange={(e) => toggleDep(d, e.target.checked)} />
                    {label}
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="fields">
              {num('children')}
              {num('youngest', '', 'yrs')}
            </div>
          </div>
        </div>
        <div className="card pad">
          <h3>You</h3>
          <div className="stack">
            <div className="fields">
              {num('income', '$')}
              {num('years', '', 'yrs')}
            </div>
            <YearsNote profile={p} />
          </div>
        </div>
        <div className="card pad">
          <h3>Debts</h3>
          <div className="stack">
            <div className="fields">
              {num('mortgage', '$')}
              {num('mortgageYears', '', 'yrs')}
            </div>
            {num('otherDebt', '$')}
          </div>
        </div>
        <div className="card pad">
          <h3>Goals and coverage</h3>
          <div className="stack">
            <div className="field">
              <label htmlFor="i_college">College</label>
              <div className="in">
                <select id="i_college" value={college} onChange={(e) => setCollege(e.target.value as College)}>
                  {(Object.entries(COLLEGE_LABEL) as [College, string][]).map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="fields">
              {num('group', '$')}
              {num('policies', '$')}
            </div>
            <div className="fields">
              {num('savings', '$')}
              {num('monthlyBudget', '$', '/mo')}
            </div>
          </div>
        </div>
        <div className="card pad">
          <h3>Coverage preferences</h3>
          <div className="stack">
            {POLICY_FIELDS.map((k) => (
              <div className="field" key={k}>
                <label htmlFor={`i_${k}`}>{LABEL[k]}</label>
                <div className="in">
                  <select id={`i_${k}`} value={prefs[k]} onChange={(e) => setPrefs({ ...prefs, [k]: e.target.value })}>
                    {prefs[k] === '' && <option value="">Choose…</option>}
                    {Object.entries(POLICY_CHOICES[k]).map(([v, l]) => (
                      <option key={v} value={v}>
                        {l}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="save-bar">
        <span className={`small status-${status.tone}`} role="status">
          {status.text}
        </span>
        <button className="btn" type="submit">
          Save changes
        </button>
      </div>
    </form>
  )
}

/* Account: change the password (other devices are signed out), or explain how a Google-only account adds one. */
function AccountSettings() {
  const { account, changePassword } = useApp()
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [status, setStatus] = useState<Status | null>(null)
  const [busy, setBusy] = useState(false)
  if (!account) return null

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (busy) return
    if (!current) return setStatus({ text: 'Enter your current password.', tone: 'error' })
    if (next.length < 8) return setStatus({ text: 'Use at least 8 characters for your new password.', tone: 'error' })
    if (next.length > 128) return setStatus({ text: 'Use at most 128 characters for your new password.', tone: 'error' })
    setBusy(true)
    const result = await changePassword(current, next)
    setBusy(false)
    if (!result.ok) return setStatus({ text: result.error, tone: 'error' })
    setCurrent('')
    setNext('')
    setStatus({ text: 'Password changed. Any other devices were signed out.', tone: 'ok' })
  }

  return (
    <div className="card pad spaced-lg">
      <div className="sec-head">
        <h2>Account</h2>
      </div>
      <p className="muted small flush">Signed in as {account.email}</p>
      {account.hasPassword ? (
        <form className="stack account-form" onSubmit={submit} noValidate>
          <h3>Change password</h3>
          {/* Lets password managers update the right saved login. */}
          <input type="email" name="username" autoComplete="username" value={account.email} readOnly hidden />
          <div className="field">
            <label htmlFor="curPass">Current password</label>
            <div className="in">
              <input id="curPass" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
            </div>
          </div>
          <div className="field">
            <label htmlFor="nextPass">New password</label>
            <div className="in">
              <input id="nextPass" type="password" autoComplete="new-password" placeholder="At least 8 characters" value={next} onChange={(e) => setNext(e.target.value)} />
            </div>
          </div>
          <span className={`small status-${status?.tone ?? 'muted'}`} role="status">
            {status?.text}
          </span>
          <button className="btn" type="submit" disabled={busy}>
            {busy ? 'One moment…' : 'Change password'}
          </button>
        </form>
      ) : (
        <p className="small">
          You sign in with Google. To also sign in with a password, use "Forgot password?" on the log-in page and we'll email
          you a link to set one.
        </p>
      )}
      <DeleteAccount hasPassword={account.hasPassword} />
    </div>
  )
}

/* Delete the account and its saved answers, after a second step (and the password, if it has one). */
function DeleteAccount({ hasPassword }: { hasPassword: boolean }) {
  const { deleteAccount } = useApp()
  const [open, setOpen] = useState(false)
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (busy) return
    if (hasPassword && !password) return setError('Enter your password to confirm.')
    setBusy(true)
    const result = await deleteAccount(hasPassword ? password : null)
    setBusy(false)
    if (!result.ok) setError(result.error)
  }

  return (
    <div className="stack account-form">
      <h3>Your saved answers</h3>
      <p className="small flush">
        Your answers are saved to your account so you can pick up on any device. We keep them until you delete your account, and
        delete accounts that haven't been signed in to for 180 days. They're never used for anything but your estimate.
      </p>
      {open ? (
        <form className="stack danger-zone" onSubmit={submit} noValidate>
          <p className="small flush">
            This permanently deletes your account, your saved answers and change log, and any callback requests you sent while
            signed in. It can't be undone.
          </p>
          {hasPassword && (
            <div className="field">
              <label htmlFor="deletePass">Your password</label>
              <div className="in">
                <input id="deletePass" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
              </div>
            </div>
          )}
          <div className="err" role="alert">
            {error}
          </div>
          <div className="row-actions">
            <button className="btn danger" type="submit" disabled={busy}>
              {busy ? 'Deleting…' : 'Delete permanently'}
            </button>
            <button className="btn ghost" type="button" onClick={() => setOpen(false)}>
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <button className="btn ghost" type="button" onClick={() => setOpen(true)}>
          Delete my account and answers
        </button>
      )}
    </div>
  )
}

/** How a save moved the starting point: a sentence for the status line, and a change-log entry when it moved. */
function movement(before: number, after: number): { sentence: string; log: string | null } {
  if (before === after) return { sentence: `Your starting point stays at ${fmt(after)}.`, log: null }
  const diff = after - before
  const way = diff > 0 ? 'up' : 'down'
  return {
    sentence: `Your starting point went from ${fmt(before)} to ${fmt(after)} (${way} ${fmt(Math.abs(diff))}).`,
    log: `Starting point: ${fmt(before)} → ${fmt(after)} (${way} ${fmt(Math.abs(diff))})`,
  }
}

/** Explains when the estimate uses more years than entered, so support lasts until the youngest turns 18. */
function YearsNote({ profile }: { profile: Profile }) {
  const c = compute(profile)
  if (c.years <= c.yearsEntered) return null
  return (
    <p className="muted small flush" data-testid="years-note">
      The estimate uses {c.years} years, not {c.yearsEntered}, so income support lasts until your youngest turns {ADULT_AGE}.
    </p>
  )
}
