import { describe, expect, it } from 'vitest'
import { explainInPlace, explainLeft, explainNeed, explainRange, explainTerm } from './explain'
import { compute } from './needs'
import { EXAMPLE, blankProfile } from './profile'

const c = compute(EXAMPLE)

describe('number explanations (Maya example)', () => {
  it('coverage in place', () => {
    expect(explainInPlace(EXAMPLE, c)).toBe(
      '$156,000 through work + $0 in policies you own + $20,000 in savings you counted = $176,000. That covers about 11% of the estimated need.',
    )
  })

  it('estimated need adds up every line', () => {
    expect(explainNeed(c)).toBe(
      'Income replacement $1,111,500 + Debts to clear $258,000 + College $200,000 + Final expenses $15,000 = $1,584,500. See the Breakdown tab for how each part is figured.',
    )
  })

  it('left to cover and the rounded starting point', () => {
    expect(explainLeft(c)).toBe(
      'Estimated need $1,584,500 − coverage in place $176,000 = $1,408,500. Rounded up to the nearest $25,000, that gives a starting point of $1,425,000.',
    )
  })

  it('left to cover when already covered', () => {
    const covered = compute({ ...blankProfile(), deps: ['none'], otherDebt: 20000, group: 50000 })
    expect(explainLeft(covered)).toBe('What you have ($50,000) already meets the estimated need ($35,000), so nothing is left to cover.')
  })

  it('term length names the longest need', () => {
    expect(explainTerm(EXAMPLE, c)).toBe(
      'Your longest need is 26 years (19 years of income support, 26 years left on the mortgage). Term policies usually come in 10, 15, 20, 25 or 30 years, so this rounds up to 30.',
    )
  })

  it('range', () => {
    expect(explainRange(c)).toBe("About 15% below and above the $1,408,500 left to cover, rounded to $25,000 steps. It's a band to compare against, not a quote.")
  })
})
