import { useRef, useState, type FormEvent } from 'react'
import { shortDate } from '../domain/format'
import { ADULT_AGE, compute } from '../domain/needs'
import {
  COLLEGE_LABEL,
  INT_FIELDS,
  LABEL,
  MONEY_FIELDS,
  isInt,
  showVal,
  type College,
  type Dep,
  type Field,
  type NumberField,
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
  const { profile, isExample, log, saveInfo } = useApp()
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
      <InfoForm key={JSON.stringify(profile)} profile={profile} status={status} setStatus={setStatus} onSave={saveInfo} />
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
    </>
  )
}

interface FormProps {
  profile: Profile
  status: Status
  setStatus: (s: Status) => void
  onSave: (next: Profile, changes: string[]) => void
}

function InfoForm({ profile: p, status, setStatus, onSave }: FormProps) {
  const [deps, setDeps] = useState<Dep[]>(p.deps)
  const [college, setCollege] = useState<College>(p.college)
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
    const changed = ([...NUMBER_FIELDS, 'deps', 'college'] as Field[]).filter((k) => JSON.stringify(next[k]) !== JSON.stringify(p[k]))
    if (!changed.length) return setStatus({ text: 'Nothing changed.', tone: 'error' })
    setStatus({
      text: `Saved ${changed.length} change${changed.length > 1 ? 's' : ''}. Your dashboard and breakdown are updated.`,
      tone: 'ok',
    })
    onSave(
      next,
      changed.map((k) => `${LABEL[k]}: ${showVal(k, p)} → ${showVal(k, next)}`),
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
              {num('age', '', 'yrs')}
              {num('income', '$')}
            </div>
            {num('years', '', 'yrs')}
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
            {num('savings', '$')}
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
