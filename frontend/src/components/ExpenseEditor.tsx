import { useState } from 'react'
import type { ExpenseCategory, OneTimeExpense } from '../api/types'
import { EXPENSE_CATEGORY_LABELS, formatMoney, parseWholeDollars } from '../utils/format'

interface Props {
  initial: OneTimeExpense[]
  disabled?: boolean
  onSave: (items: OneTimeExpense[]) => void
}

const CATEGORIES = Object.keys(EXPENSE_CATEGORY_LABELS) as ExpenseCategory[]

/** Edit one-time expenses. The backend allows each category at most once. */
export function ExpenseEditor({ initial, disabled, onSave }: Props) {
  const [amounts, setAmounts] = useState<Record<ExpenseCategory, string>>(() => {
    const start = Object.fromEntries(CATEGORIES.map((c) => [c, ''])) as Record<ExpenseCategory, string>
    for (const item of initial) start[item.category] = String(item.amount)
    return start
  })

  const parsed = CATEGORIES.map((category) => ({ category, raw: amounts[category].trim() }))
  const invalid = parsed.some(({ raw }) => raw !== '' && parseWholeDollars(raw) === null)
  const items: OneTimeExpense[] = parsed
    .filter(({ raw }) => raw !== '' && parseWholeDollars(raw) !== null)
    .map(({ category, raw }) => ({
      id: category,
      label: EXPENSE_CATEGORY_LABELS[category],
      category,
      amount: parseWholeDollars(raw)!,
    }))
  const total = items.reduce((sum, i) => sum + i.amount, 0)

  return (
    <div className="expense-editor">
      {CATEGORIES.map((category) => (
        <label key={category} className="field-row">
          <span>{EXPENSE_CATEGORY_LABELS[category]}</span>
          <input
            inputMode="numeric"
            placeholder="$0"
            value={amounts[category]}
            disabled={disabled}
            onChange={(e) => setAmounts((a) => ({ ...a, [category]: e.target.value }))}
          />
        </label>
      ))}
      <p className="muted">
        Total: <strong>{formatMoney(total)}</strong>
        {invalid && <span className="error-text"> · Whole dollar amounts only</span>}
      </p>
      <button type="button" disabled={disabled || invalid} onClick={() => onSave(items)}>
        {items.length === 0 ? 'No one-time expenses' : 'Save expenses'}
      </button>
    </div>
  )
}
