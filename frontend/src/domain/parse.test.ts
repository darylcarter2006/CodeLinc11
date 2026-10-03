import { describe, expect, it } from 'vitest'
import { applyUpdates, clean, parseLocal } from './parse'
import { blankProfile, blankSaved, type Field, type Profile } from './profile'

const p = (over: Partial<Profile> = {}): Profile => ({ ...blankProfile(), ...over })

describe('parseLocal', () => {
  const cases: [Field, string, Partial<Profile>, unknown][] = [
    ['income', 'about 85k', {}, 85000],
    ['income', '$240,000', {}, 240000],
    ['income', '1.2m', {}, 1200000],
    ['savings', '2 million', {}, 2000000],
    ['savings', 'none', {}, 0],
    ['otherDebt', 'nothing really', {}, 0],
    ['policies', 'zero', {}, 0],
    ['group', '2x salary', { income: 90000 }, 180000],
    ['group', '1.5 times my pay', { income: 80000 }, 120000],
    ['group', '$50,000', { income: 80000 }, 50000],
    ['deps', 'me and my wife plus our kids', {}, ['partner', 'kids']],
    ['deps', 'my mom', {}, ['relative']],
    ['deps', 'Just me', {}, ['none']],
    ['deps', 'no one', {}, ['none']],
    ['deps', 'hmm', {}, undefined],
    ['years', 'until my youngest is 22', { deps: ['kids'], youngest: 4 }, 18],
    ['years', 'Until my youngest is 22', { deps: ['kids'], youngest: 3 }, 19],
    ['years', 'until they are grown', { deps: ['kids'], youngest: 20 }, 5],
    ['years', '15 years', {}, 15],
    ['college', 'not part of the plan', {}, 'none'],
    ['college', 'About half', {}, 'half'],
    ['college', 'Yes, public in-state', {}, 'public'],
    ['mortgage', 'we rent', {}, 0],
    ['mortgage', 'No mortgage', {}, 0],
    ['children', 'three', {}, 3],
    ['children', '2', {}, 2],
    ['age', 'not sure', {}, undefined],
  ]

  it.each(cases)('%s: "%s"', (field, text, profile, expected) => {
    expect(parseLocal(field, text, p(profile))).toEqual(expected)
  })
})

describe('clean', () => {
  it('rejects bad enums, negatives and unknown keys', () => {
    expect(clean({ deps: ['partner', 'pet'], college: 'ivy', income: -5, ssn: '123', age: 'old' })).toEqual({ deps: ['partner'] })
  })

  it('collapses deps containing none', () => {
    expect(clean({ deps: ['partner', 'none'] })).toEqual({ deps: ['none'] })
  })

  it('drops an empty deps list', () => {
    expect(clean({ deps: ['cat'] })).toEqual({})
  })

  it('rounds numbers and caps age-like fields at 120', () => {
    expect(clean({ income: 85000.6, age: 150, years: 19.4, savings: '25000' })).toEqual({ income: 85001, age: 120, years: 19, savings: 25000 })
  })

  it('ignores non-objects, nulls and booleans', () => {
    expect(clean(null)).toEqual({})
    expect(clean('income')).toEqual({})
    expect(clean({ income: null, savings: true })).toEqual({})
  })
})

describe('applyUpdates', () => {
  it('marks fields known', () => {
    const s = applyUpdates({ income: 50000 }, blankSaved())
    expect(s.known).toEqual(['income'])
    expect(s.p.income).toBe(50000)
  })

  it('no dependents sets years to 0 and clears kid fields', () => {
    const start = { ...blankSaved(), p: p({ deps: ['kids'], years: 19, children: 2, youngest: 3, college: 'public' }) }
    const s = applyUpdates({ deps: ['none'] }, start)
    expect(s.p).toMatchObject({ years: 0, children: 0, youngest: 0, college: 'none' })
  })

  it('no mortgage zeroes and marks mortgage years', () => {
    const s = applyUpdates({ mortgage: 0 }, { ...blankSaved(), p: p({ mortgageYears: 12 }) })
    expect(s.p.mortgageYears).toBe(0)
    expect(s.known).toEqual(['mortgage', 'mortgageYears'])
  })

  it('does not mutate the input', () => {
    const start = blankSaved()
    applyUpdates({ income: 1 }, start)
    expect(start).toEqual(blankSaved())
  })
})
