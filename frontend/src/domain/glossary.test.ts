import { describe, expect, it } from 'vitest'
import { GLOSSARY, findTerms } from './glossary'

describe('findTerms', () => {
  it('marks glossary terms and keeps the surrounding text', () => {
    expect(findTerms('Term life covers a set number of years.')).toEqual([{ key: 'term', text: 'Term life' }, ' covers a set number of years.'])
  })

  it('marks only the first mention of each term', () => {
    const parts = findTerms('Laddering means laddered policies. Laddering can lower cost.')
    expect(parts.filter((p) => typeof p !== 'string')).toEqual([{ key: 'laddering', text: 'Laddering' }])
  })

  it('matches whole words only', () => {
    expect(findTerms('Rates may change permanently.')).toEqual(['Rates may change permanently.'])
  })

  it('returns plain text unchanged when there are no terms', () => {
    expect(findTerms('Debts to clear')).toEqual(['Debts to clear'])
  })

  it('has a definition for every entry', () => {
    for (const entry of Object.values(GLOSSARY)) {
      expect(entry.definition.length).toBeGreaterThan(20)
      expect(entry.matches.length).toBeGreaterThan(0)
    }
  })
})
