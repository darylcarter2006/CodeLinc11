import { describe, expect, it } from 'vitest'
import { compute, nextSteps, tradeoffs } from './needs'
import { EXAMPLE, blankProfile, type Profile } from './profile'

const halfCollege: Profile = {
  deps: ['partner', 'kids'],
  children: 2,
  youngest: 4,
  age: 0,
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
    expect(compute({ ...EXAMPLE, years: 8, mortgageYears: 26 }).term).toBe(30)
    expect(compute({ ...EXAMPLE, years: 8, mortgage: 0, mortgageYears: 26 }).term).toBe(10)
  })
})

describe('tradeoffs and next steps', () => {
  it('builds every applicable card for Maya, term vs. whole first', () => {
    const tags = tradeoffs(EXAMPLE, compute(EXAMPLE)).map((t) => t.tag)
    expect(tags).toEqual(['Term or whole', 'Term length', 'Laddering', 'Work coverage', 'Savings', 'College'])
  })

  it('shows the fewer-dependents card when no one relies on them', () => {
    const tags = tradeoffs(alreadyCovered, compute(alreadyCovered)).map((t) => t.tag)
    expect(tags).toContain('Fewer dependents')
  })

  it('lists next steps from the rules', () => {
    expect(nextSteps(EXAMPLE, compute(EXAMPLE))).toEqual([
      'Compare term quotes for about $1.43M over 30 years',
      'Ask HR whether your work coverage can be converted or kept if you leave',
      'Check the beneficiaries on your existing coverage',
      'Price one policy vs. two shorter, laddered policies',
      'Update My info after a new child, home or job',
    ])
  })
})
