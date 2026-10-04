import { describe, expect, it } from 'vitest'
import { applyUpdates, parseLocal } from './parse'
import { blankSaved, nextStep, type Field } from './profile'

/** Run the onboarding conversation with typed answers; returns the questions in the order asked. */
function converse(answers: Partial<Record<Field, string>>): Field[] {
  let saved = blankSaved()
  const asked: Field[] = []
  for (let step = nextStep(saved); step; step = nextStep(saved)) {
    asked.push(step.k)
    const reply = answers[step.k]
    if (reply === undefined) throw new Error(`no scripted answer for ${step.k}`)
    saved = applyUpdates({ [step.k]: parseLocal(step.k, reply, saved.p) }, saved)
  }
  return asked
}

const COVERAGE_TYPE: Partial<Record<Field, string>> = {
  coverFor: 'A specific period',
  budget: 'Lowest monthly cost',
  cashValue: 'no',
  legacy: 'no',
  simple: 'Keep it simple',
}

describe('the conversation adapts to this person', () => {
  it('a parent with a mortgage is asked about children, years of support, the mortgage term and college', () => {
    const asked = converse({
      deps: 'Partner and kids',
      children: '2',
      youngest: '3',
      income: '$78k',
      years: 'Until my youngest is 22',
      mortgage: '$240,000',
      mortgageYears: '26',
      otherDebt: '18000',
      college: 'Yes, public in-state',
      group: '2x salary',
      policies: 'None',
      savings: '$20k',
      monthlyBudget: '$60',
      ...COVERAGE_TYPE,
    })
    expect(asked).toEqual([
      'deps', 'children', 'youngest', 'income', 'years', 'mortgage', 'mortgageYears', 'otherDebt', 'college',
      'group', 'policies', 'savings', 'monthlyBudget', 'coverFor', 'budget', 'cashValue', 'legacy', 'simple',
    ]) // prettier-ignore
  })

  it('someone with no dependants who rents skips children, years of support, the mortgage term and college', () => {
    const asked = converse({
      deps: 'No one',
      income: '$60k',
      mortgage: 'No mortgage',
      otherDebt: 'None',
      group: 'None',
      policies: 'None',
      savings: 'None',
      monthlyBudget: 'Not sure',
      ...COVERAGE_TYPE,
    })
    expect(asked).toEqual([
      'deps', 'income', 'mortgage', 'otherDebt', 'group', 'policies', 'savings', 'monthlyBudget',
      'coverFor', 'budget', 'cashValue', 'legacy', 'simple',
    ]) // prettier-ignore
  })

  it('a couple without children with a mortgage gets years of support and the mortgage term, but no child questions', () => {
    const asked = converse({
      deps: 'My partner',
      income: '$90k',
      years: '15 years',
      mortgage: '$300k',
      mortgageYears: '20',
      otherDebt: 'None',
      group: '1x salary',
      policies: 'None',
      savings: 'None',
      monthlyBudget: '$50',
      ...COVERAGE_TYPE,
    })
    expect(asked).toContain('years')
    expect(asked).toContain('mortgageYears')
    expect(asked).not.toContain('children')
    expect(asked).not.toContain('college')
  })
})
