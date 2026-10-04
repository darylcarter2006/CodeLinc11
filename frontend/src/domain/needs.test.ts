import { describe, expect, it } from 'vitest'
import { compute, nextSteps, tradeoffs } from './needs'
import { EXAMPLE, blankProfile, type Profile } from './profile'

const halfCollege: Profile = {
  ...blankProfile(),
  deps: ['partner', 'kids'],
  children: 2,
  youngest: 4,
  income: 85000,
  years: 18,
  mortgage: 210000,
  mortgageYears: 22,
  otherDebt: 12000,
  college: 'half',
  group: 170000,
  policies: 0,
  savings: 15000,
}

const alreadyCovered: Profile = { ...blankProfile(), deps: ['none'], income: 60000, otherDebt: 20000, group: 50000 }

describe('compute (handoff test vectors)', () => {
  it('Maya example', () => {
    const c = compute(EXAMPLE)
    expect(c).toMatchObject({ total: 1584500, existing: 176000, gap: 1408500, suggested: 1425000, low: 1175000, high: 1625000, term: 30 })
    expect(c.lines.map((l) => l.amt)).toEqual([1111500, 258000, 200000, 15000])
  })

  it('half college', () => {
    expect(compute(halfCollege)).toMatchObject({ total: 1484500, existing: 185000, gap: 1299500, suggested: 1300000, term: 25 })
  })

  it('already covered', () => {
    const c = compute(alreadyCovered)
    expect(c).toMatchObject({ total: 35000, existing: 50000, gap: 0, suggested: 0, term: 10 })
    expect(c.lines[0].how).toBe('No one relies on your income, so none is needed')
  })
})

describe('compute rounding and term edges', () => {
  const withGap = (gap: number) => compute({ ...blankProfile(), deps: ['none'], otherDebt: gap - 15000 })

  it('keeps an exact multiple of $25,000', () => {
    expect(withGap(100000).suggested).toBe(100000)
  })

  it('rounds up by a single dollar over', () => {
    expect(withGap(100001).suggested).toBe(125000)
  })

  it('rounds the range down and up', () => {
    const c = withGap(100000)
    expect([c.low, c.high]).toEqual([75000, 125000])
  })

  it('ignores years and children that do not apply', () => {
    const c = compute({ ...EXAMPLE, deps: ['partner'], children: 3 })
    expect(c.kids).toBe(0)
    expect(c.lines[2].amt).toBe(0)
    expect(compute({ ...EXAMPLE, deps: ['none'] }).years).toBe(0)
  })

  it('caps the term at 30 years', () => {
    expect(compute({ ...EXAMPLE, years: 40 }).term).toBe(30)
  })

  it('uses mortgage years only when there is a mortgage', () => {
    expect(compute({ ...EXAMPLE, youngest: 15, years: 8, mortgageYears: 26 }).term).toBe(30)
    expect(compute({ ...EXAMPLE, youngest: 15, years: 8, mortgage: 0, mortgageYears: 26 }).term).toBe(10)
  })
})

describe("years of support reach the youngest child's 18th birthday", () => {
  const family = (youngest: number, years: number): Profile => ({ ...EXAMPLE, youngest, years, mortgage: 0 })

  it('uses the years until the youngest turns 18 when more than entered, and says so', () => {
    const c = compute(family(2, 15))
    expect(c.years).toBe(16)
    expect(c.yearsEntered).toBe(15)
    expect(c.lines[0].amt).toBe(78000 * 0.75 * 16)
    expect(c.lines[0].how).toBe('75% of $78,000 × 16 years (until your youngest turns 18; you entered 15)')
  })

  it('keeps the entered years when they already reach 18 or the youngest is grown', () => {
    expect(compute(family(3, 19)).years).toBe(19)
    expect(compute(family(20, 15)).years).toBe(15)
    expect(compute(family(20, 15)).lines[0].how).toBe('75% of $78,000 × 15 years')
  })

  it('only applies when children are among the dependents', () => {
    expect(compute({ ...family(2, 15), deps: ['partner'] }).years).toBe(15)
    expect(compute({ ...family(2, 15), deps: ['none'] }).years).toBe(0)
  })

  it('feeds the longer window into the suggested term', () => {
    expect(compute(family(0, 5)).term).toBe(20)
  })
})

describe('tradeoffs and next steps', () => {
  it('builds every applicable card for Maya, term vs. whole first', () => {
    const tags = tradeoffs(EXAMPLE, compute(EXAMPLE)).map((t) => t.tag)
    expect(tags).toEqual(['Term or whole', 'Term length', 'Laddering', 'Work coverage', 'Savings', 'College', 'Budget'])
  })

  it('works out the budget from what they said they can afford', () => {
    const c = compute(EXAMPLE)
    expect(c.budget).toEqual({ monthly: 60, yearly: 720, overTerm: 720 * c.term })
    const card = tradeoffs(EXAMPLE, c).find((t) => t.tag === 'Budget')!
    expect(card.title).toBe('Fitting $60 a month')
    expect(card.body).toContain(`$720 a year, or ${'$' + (720 * c.term).toLocaleString('en-US')} over a ${c.term}-year term`)
    expect(card.body).toContain('a 25-year term instead of 30')
    expect(card.body).toContain('about half of college')
  })

  it('has no budget figures or card when they were not sure', () => {
    const p = { ...EXAMPLE, monthlyBudget: 0 }
    expect(compute(p).budget).toBeNull()
    expect(tradeoffs(p, compute(p)).map((t) => t.tag)).not.toContain('Budget')
  })

  it('ranks what the need is made of, largest first, with each share', () => {
    const d = compute(EXAMPLE).drivers
    expect(d.map((x) => [x.label, x.share])).toEqual([
      ['Income replacement', 70],
      ['Debts to clear', 16],
      ['College', 13],
      ['Final expenses', 1],
    ])
    expect(d[0].answers).toBe('your income and years of support')
  })

  it('shows the fewer-dependents card when no one relies on them', () => {
    const tags = tradeoffs(alreadyCovered, compute(alreadyCovered)).map((t) => t.tag)
    expect(tags).toContain('Fewer dependents')
  })

  it('lists next steps from the rules', () => {
    expect(nextSteps(EXAMPLE, compute(EXAMPLE))).toEqual([
      'Review the $1.43M, 30-year estimate with a licensed Lincoln Financial representative',
      'Ask HR whether your work coverage can be converted or kept if you leave',
      'Check the beneficiaries on your existing coverage',
      'Learn how one policy compares with two shorter, laddered policies',
      'Update My info after a new child, home or job',
    ])
  })
})
