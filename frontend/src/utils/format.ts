import type { ExpenseCategory, ProfileFieldName, ProfileValue } from '../api/types'

const usd = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})

/**
 * Full dollar amounts, never abbreviated ("$1,250,000", not "$1.3M"), so nothing is
 * rounded away. Negative offsets use a real minus sign.
 */
export function formatMoney(amount: number): string {
  return amount < 0 ? `−${usd.format(-amount)}` : usd.format(amount)
}

/** Mirrors FIELD_SPECS labels in backend/app/domain/profile.py. */
export const FIELD_LABELS: Record<ProfileFieldName, string> = {
  dependents_count: 'Number of dependents',
  youngest_dependent_age: "Youngest dependent's age",
  annual_support_need: 'Annual household spending to support',
  annual_survivor_contribution: 'Continuing annual income',
  support_years: 'Years of support',
  one_time_expenses: 'One-time expenses',
  available_assets: 'Assets you chose to count',
  personal_coverage: 'Personal life insurance',
  employer_coverage: 'Employer life insurance',
  budget_monthly: 'Monthly budget for coverage',
}

export const MONEY_FIELDS: ReadonlySet<ProfileFieldName> = new Set([
  'annual_support_need',
  'annual_survivor_contribution',
  'available_assets',
  'personal_coverage',
  'employer_coverage',
  'budget_monthly',
])

export const EXPENSE_CATEGORY_LABELS: Record<ExpenseCategory, string> = {
  final_expenses: 'Final expenses',
  education: 'Education',
  debt_payoff: 'Debt payoff',
  mortgage_payoff: 'Mortgage payoff',
  other: 'Other',
}

export function fieldLabel(name: string): string {
  return FIELD_LABELS[name as ProfileFieldName] ?? name.replace(/_/g, ' ')
}

/** Human-readable value for a profile field, including the "not asked" and "unknown" states. */
export function formatFieldValue(name: ProfileFieldName, field: ProfileValue<unknown> | null): string {
  if (field === null) return 'Not answered yet'
  if (field.value === null) return "Don't know"
  if (name === 'one_time_expenses') {
    const items = field.value as { amount: number }[]
    if (items.length === 0) return 'None'
    return `${formatMoney(items.reduce((sum, i) => sum + i.amount, 0))} (${items.length} item${items.length === 1 ? '' : 's'})`
  }
  if (MONEY_FIELDS.has(name)) return formatMoney(field.value as number)
  return String(field.value)
}

/** Parse "$80,000" / "80000" into whole dollars; returns null if not a nonnegative integer. */
export function parseWholeDollars(input: string): number | null {
  const cleaned = input.replace(/[$,\s]/g, '')
  if (!/^\d+$/.test(cleaned)) return null
  return Number(cleaned)
}
