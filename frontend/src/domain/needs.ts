import { fmt, short } from './format'
import { hasDep, type College, type Profile } from './profile'

/* Needs calculation. Deterministic and ported exactly from the prototype; the AI only explains it. */

export const ASSUMPTIONS = {
  replace: 0.75,
  final: 15000,
  college: { public: 100000, half: 50000, none: 0 } as Record<College, number>,
}

const STEP = 25000
/** Income support covers at least the years until the youngest child reaches this age. */
export const ADULT_AGE = 18
const TERMS = [10, 15, 20, 25, 30]

export type LineKey = 'c1' | 'c2' | 'c3' | 'c4'

export interface Line {
  key: LineKey
  label: string
  amt: number
  how: string
}

export interface Calculation {
  lines: Line[]
  total: number
  existing: number
  gap: number
  suggested: number
  low: number
  high: number
  /** Years of income support used: the entered years, or more to reach the youngest's 18th birthday. */
  years: number
  /** Years the user entered (0 when no one relies on their income). */
  yearsEntered: number
  kids: number
  term: number
  termNeed: number
}

const roundUp = (v: number) => Math.ceil(v / STEP) * STEP

export function compute(p: Profile): Calculation {
  const kids = hasDep(p, 'kids') ? p.children : 0
  const yearsEntered = hasDep(p, 'none') ? 0 : p.years
  // Support lasts at least until the youngest child turns 18, and the explanation says when that applies.
  const untilAdult = kids > 0 ? Math.max(0, ADULT_AGE - p.youngest) : 0
  const years = Math.max(yearsEntered, untilAdult)
  const extended = years > yearsEntered
  const perChild = ASSUMPTIONS.college[p.college || 'none']
  const lines: Line[] = [
    {
      key: 'c1',
      label: 'Income replacement',
      amt: p.income * ASSUMPTIONS.replace * years,
      how: years
        ? `75% of ${fmt(p.income)} × ${years} years` +
          (extended ? ` (until your youngest turns ${ADULT_AGE}; you entered ${yearsEntered})` : '')
        : 'No one relies on your income, so none is needed',
    },
    {
      key: 'c2',
      label: 'Debts to clear',
      amt: p.mortgage + p.otherDebt,
      how: `${fmt(p.mortgage)} mortgage + ${fmt(p.otherDebt)} other debts`,
    },
    {
      key: 'c3',
      label: 'College',
      amt: kids * perChild,
      how: kids ? `${kids} ${kids > 1 ? 'children' : 'child'} × ${fmt(perChild)}` : 'No children included',
    },
    { key: 'c4', label: 'Final expenses', amt: ASSUMPTIONS.final, how: 'Typical funeral and settling costs' },
  ]
  const total = lines.reduce((s, l) => s + l.amt, 0)
  const existing = p.group + p.policies + p.savings
  const gap = Math.max(0, total - existing)
  const termNeed = Math.max(years, p.mortgage > 0 ? p.mortgageYears : 0)
  const term = TERMS.find((t) => t >= termNeed) ?? 30
  return {
    lines,
    total,
    existing,
    gap,
    suggested: roundUp(gap),
    low: Math.floor((gap * 0.85) / STEP) * STEP,
    high: roundUp(gap * 1.15),
    years,
    yearsEntered,
    kids,
    term,
    termNeed,
  }
}

/** Covered share of the need, 0-100. */
export const coveredPct = (c: Calculation) => (c.total ? Math.min(100, Math.round((c.existing / c.total) * 100)) : 100)

/** Mortgage and income support end far enough apart that two policies are worth pricing. */
export const laddering = (p: Profile, c: Calculation) =>
  p.mortgage > 0 && c.years > 0 && Math.abs(p.mortgageYears - c.years) >= 5

export interface Tradeoff {
  tag: string
  title: string
  body: string
  pair?: [string, string][]
}

/* Personalized tradeoffs: rules over the user's own numbers. */
export function tradeoffs(p: Profile, c: Calculation): Tradeoff[] {
  const t: Tradeoff[] = []
  const temp = c.total ? Math.round(((c.lines[0].amt + c.lines[1].amt) / c.total) * 100) : 0
  t.push({
    tag: 'Term or whole',
    title: 'Term vs. whole life for you',
    body:
      `About ${temp}% of your need is income and debt that shrink over time. Term life covers a set number of years and buys the most coverage per dollar, which fits that shape. Whole life lasts your entire life and builds cash value, but often costs many times more for the same amount.` +
      (hasDep(p, 'relative')
        ? ' Because a parent or relative relies on you, a small permanent policy alongside term may be worth a look.'
        : ' Some people pair a large term policy with a small permanent one for final expenses.'),
    pair: [
      ['Term', `${short(c.suggested)} for ${c.term} years. Lower cost, ends on schedule.`],
      ['Whole', 'Lifelong, builds cash value. Much higher cost for the same amount.'],
    ],
  })
  if (c.years > 0 && c.term > 10) {
    const shorter = [10, 15, 20, 25].filter((x) => x < c.term).pop()!
    const why = c.kids ? `your youngest is ${p.youngest + c.term}` : `${c.term} years from now`
    t.push({
      tag: 'Term length',
      title: `${c.term} years or ${shorter}?`,
      body: `A ${c.term}-year term runs until ${why}${p.mortgageYears >= c.years && p.mortgage ? ' and outlasts your mortgage' : ''}. A ${shorter}-year term costs less, but ends ${c.term - shorter} years sooner${c.kids ? `, when your youngest is ${p.youngest + shorter}` : ''}.`,
    })
  }
  if (laddering(p, c)) {
    const inc = roundUp(c.lines[0].amt + c.lines[2].amt)
    const mort = roundUp(p.mortgage)
    const [a, b] =
      p.mortgageYears > c.years
        ? [
            [inc, c.years],
            [mort, p.mortgageYears],
          ]
        : [
            [mort, p.mortgageYears],
            [inc, c.years],
          ]
    t.push({
      tag: 'Laddering',
      title: 'One policy or two?',
      body: `Your income need and your mortgage end at different times (${c.years} vs. ${p.mortgageYears} years). Two policies, such as ${short(a[0])} for ${a[1]} years and ${short(b[0])} for ${b[1]} years, let coverage step down as needs shrink, which can lower total cost.`,
    })
  }
  if (p.group > 0) {
    const without = compute({ ...p, group: 0 })
    t.push({
      tag: 'Work coverage',
      title: 'Counting coverage from work',
      body: `${fmt(p.group)} of your existing coverage comes through your employer. It usually ends if you change jobs. Leaving it out would raise the starting point to ${fmt(without.suggested)}.`,
    })
  }
  if (p.savings > 0)
    t.push({
      tag: 'Savings',
      title: 'Counting your savings',
      body: `Counting ${fmt(p.savings)} of savings lowers the coverage you need. The tradeoff: that money then can't also serve as your emergency fund or retirement savings.`,
    })
  if (c.kids && p.college === 'public') {
    const half = compute({ ...p, college: 'half' })
    t.push({
      tag: 'College',
      title: 'Fully funding college',
      body: `Covering public in-state college adds ${fmt(c.lines[2].amt)}. Planning for about half would bring the starting point to ${fmt(half.suggested)}, with the rest from savings, aid or work.`,
    })
  }
  if (hasDep(p, 'none'))
    t.push({
      tag: 'Fewer dependents',
      title: 'A smaller policy may be enough',
      body: "With no one relying on your income, coverage mainly clears debts and final costs so they don't pass to family. You can revisit this if your situation changes.",
    })
  return t
}

export function nextSteps(p: Profile, c: Calculation): string[] {
  const s: string[] = []
  if (c.gap > 0) s.push(`Compare term quotes for about ${short(c.suggested)} over ${c.term} years`)
  if (p.group > 0) s.push('Ask HR whether your work coverage can be converted or kept if you leave')
  if (p.group > 0 || p.policies > 0) s.push('Check the beneficiaries on your existing coverage')
  if (laddering(p, c)) s.push('Price one policy vs. two shorter, laddered policies')
  s.push('Update My info after a new child, home or job')
  return s
}
