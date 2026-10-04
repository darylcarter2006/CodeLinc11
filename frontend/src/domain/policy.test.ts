import { describe, expect, it } from 'vitest'
import { clean, parseLocal } from './parse'
import { policyAnswered, policyFit } from './policy'
import { EXAMPLE, POLICY_FIELDS, blankProfile, blankSaved, type Profile } from './profile'

const prefs = (overrides: Partial<Profile>): Profile => ({ ...blankProfile(), ...overrides })

describe('policyFit (hidden tally)', () => {
  it('all-term answers give term 5-0', () => {
    expect(policyFit(prefs({}))).toMatchObject({ type: 'term', term: 5, perm: 0 })
  })

  it('all-permanent answers give permanent 0-5', () => {
    const p = prefs({ coverFor: 'lifelong', budget: 'more', cashValue: 'yes', legacy: 'yes', simple: 'no' })
    expect(policyFit(p)).toMatchObject({ type: 'perm', term: 0, perm: 5 })
  })

  it('the higher score wins', () => {
    const p = prefs({ coverFor: 'lifelong', cashValue: 'yes', legacy: 'yes' })
    expect(policyFit(p)).toMatchObject({ type: 'perm', term: 2, perm: 3 })
  })

  it('a tie goes to term (only possible when a question is skipped)', () => {
    const p = prefs({ coverFor: 'lifelong', cashValue: 'yes' })
    const known = ['coverFor', 'budget', 'cashValue', 'legacy'] as const
    expect(policyFit(p, known)).toMatchObject({ type: 'term', term: 2, perm: 2 })
  })

  it('only answered questions count', () => {
    expect(policyFit(prefs({}), ['coverFor'])).toMatchObject({ term: 1, perm: 0 })
    expect(policyFit(prefs({}), []).reasons).toEqual([])
  })

  it('gives one reason per answer', () => {
    const fit = policyFit(prefs({ legacy: 'yes' }))
    expect(fit.reasons).toHaveLength(5)
    expect(fit.reasons.find((r) => r.field === 'legacy')).toMatchObject({ side: 'perm', text: expect.stringMatching(/heirs/) })
  })

  it('the example profile fits term', () => {
    expect(policyFit(EXAMPLE).type).toBe('term')
  })

  it('needs every question answered before showing a result', () => {
    expect(policyAnswered(blankSaved())).toBe(false)
    expect(policyAnswered({ ...blankSaved(), known: [...POLICY_FIELDS] })).toBe(true)
  })
})

describe('parsing coverage-type answers', () => {
  const p = blankProfile()
  it.each([
    ['coverFor', 'A specific period', 'period'],
    ['coverFor', 'my whole life', 'lifelong'],
    ['coverFor', 'until the kids are grown', 'period'],
    ['coverFor', 'forever, I guess', 'lifelong'],
    ['budget', 'Lowest monthly cost', 'lowest'],
    ['budget', "I'd pay more for benefits", 'more'],
    ['budget', 'cheapest please', 'lowest'],
    ['cashValue', 'Yes', 'yes'],
    ['cashValue', 'nah', 'no'],
    ['legacy', "I don't care about that", 'no'],
    ['legacy', 'yes definitely', 'yes'],
    ['simple', 'Keep it simple', 'yes'],
    ['simple', 'I want extra options', 'no'],
    ['simple', 'extra options please', 'no'],
    ['simple', 'I want more features', 'no'],
    ['simple', 'simple is good', 'yes'],
    ['simple', "I don't want simple", 'no'],
    ['simple', 'yes', 'yes'],
  ] as const)('%s: "%s" → %s', (field, text, expected) => {
    expect(parseLocal(field, text, p)).toBe(expected)
  })

  it('leaves unclear answers unparsed', () => {
    expect(parseLocal('budget', 'hmm', p)).toBeUndefined()
    expect(parseLocal('cashValue', 'maybe', p)).toBeUndefined()
  })

  it('clean() keeps only known choices', () => {
    expect(clean({ coverFor: 'lifelong', budget: 'free', cashValue: 'yes', legacy: true, simple: 'toString' })).toEqual({
      coverFor: 'lifelong',
      cashValue: 'yes',
    })
  })
})
