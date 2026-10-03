import { COLLEGE_LABEL, DEPS, hasDep, hasKids, isInt, isMoney, type Dep, type Field, type Profile, type SavedProfile } from './profile'

/* Local answer parser: the only path when live AI is unavailable, and a backstop when it is. */

const WORDS: Record<string, number> = { zero: 0, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10 }
const MULT: Record<string, number> = { k: 1e3, thousand: 1e3, m: 1e6, mil: 1e6, million: 1e6 }

export function money(t: string): number | undefined {
  const m = t.match(/\$?\s*(\d[\d,]*(?:\.\d+)?)\s*(k|m|mil|million|thousand)?\b/)
  if (!m) return /\b(none|no|nothing|zero|nope|don'?t|n\/a)\b/.test(t) ? 0 : undefined
  return Math.round(parseFloat(m[1].replace(/,/g, '')) * (MULT[m[2]] || 1))
}

export function int(t: string): number | undefined {
  const m = t.match(/\d+/)
  if (m) return +m[0]
  const w = Object.keys(WORDS).find((w) => new RegExp('\\b' + w + '\\b').test(t))
  return w !== undefined ? WORDS[w] : /\b(none|no)\b/.test(t) ? 0 : undefined
}

export function parseLocal(k: Field, text: string, p: Profile): unknown {
  const t = text.toLowerCase()
  if (k === 'deps') {
    const d: Dep[] = []
    if (/partner|spouse|wife|husband|fianc/.test(t)) d.push('partner')
    if (/kid|child|son|daughter|baby/.test(t)) d.push('kids')
    if (/parent|mom|dad|mother|father|relative|grand|sibling/.test(t)) d.push('relative')
    if (!d.length && /no one|nobody|none|just me|single|myself|^no\b/.test(t)) d.push('none')
    return d.length ? d : undefined
  }
  if (k === 'years') {
    const u = t.match(/until.*?(\d+)/)
    if (u) return Math.max(1, +u[1] - (p.youngest || 0))
    if (/until/.test(t) && hasKids(p)) return Math.max(5, 22 - p.youngest)
    return int(t)
  }
  if (k === 'college')
    return /half|partial|some/.test(t) ? 'half' : /\b(no|not|none|skip)\b/.test(t) ? 'none' : /yes|public|full|all|sure|yeah/.test(t) ? 'public' : undefined
  if (k === 'group') {
    const x = t.match(/(\d+(?:\.\d+)?)\s*(x|×|times)/)
    if (x) return Math.round(+x[1] * p.income)
  }
  if (k === 'mortgage' && /rent|no mortgage|paid off/.test(t)) return 0
  return isMoney(k) ? money(t) : int(t)
}

/** Keep only well-formed values from the AI or the parser. Unknown keys are dropped. */
export function clean(u: unknown): Partial<Profile> {
  const out: Record<string, unknown> = {}
  if (!u || typeof u !== 'object') return out
  for (const [k, v] of Object.entries(u)) {
    if (k === 'deps' && Array.isArray(v)) {
      const d = v.filter((x): x is Dep => DEPS.includes(x))
      if (d.length) out.deps = d.includes('none') ? ['none'] : d
    } else if (k === 'college' && typeof v === 'string' && v in COLLEGE_LABEL) out.college = v
    else if ((isMoney(k) || isInt(k)) && v !== null && typeof v !== 'boolean' && v !== '' && isFinite(+(v as number)) && +(v as number) >= 0)
      out[k] = isInt(k) ? Math.min(120, Math.round(+(v as number))) : Math.round(+(v as number))
  }
  return out as Partial<Profile>
}

/** Merge cleaned updates, mark them known, and apply the derived rules. Returns a new SavedProfile. */
export function applyUpdates(u: Partial<Profile>, saved: SavedProfile): SavedProfile {
  const p = { ...saved.p, ...u }
  const known = [...saved.known]
  const mark = (k: Field) => {
    if (!known.includes(k)) known.push(k)
  }
  ;(Object.keys(u) as Field[]).forEach(mark)
  if ('deps' in u && hasDep(p, 'none')) p.years = 0
  if ('mortgage' in u && p.mortgage === 0) {
    p.mortgageYears = 0
    mark('mortgageYears')
  }
  if ('deps' in u && !hasKids(p)) {
    p.children = 0
    p.youngest = 0
    p.college = 'none'
  }
  return { ...saved, p, known }
}
