import { fmt } from './format'

/* Profile model and the field catalog: labels, display values, and the onboarding question order. */

export type Dep = 'partner' | 'kids' | 'relative' | 'none'
export type College = 'public' | 'half' | 'none'

export interface Profile {
  deps: Dep[]
  children: number
  youngest: number
  age: number
  income: number
  years: number
  mortgage: number
  mortgageYears: number
  otherDebt: number
  college: College
  group: number
  policies: number
  savings: number
}

export type Field = keyof Profile

export interface SavedProfile {
  p: Profile
  known: Field[]
  confirmed: boolean
  updated: number | null
}

export interface ChangeLogEntry {
  at: number
  text: string
}

export const EXAMPLE_NAME = 'Maya'

export const EXAMPLE: Profile = {
  deps: ['partner', 'kids'],
  children: 2,
  youngest: 3,
  age: 34,
  income: 78000,
  years: 19,
  mortgage: 240000,
  mortgageYears: 26,
  otherDebt: 18000,
  college: 'public',
  group: 156000,
  policies: 0,
  savings: 20000,
}

export const blankProfile = (): Profile => ({
  deps: [],
  children: 0,
  youngest: 0,
  age: 0,
  income: 0,
  years: 0,
  mortgage: 0,
  mortgageYears: 0,
  otherDebt: 0,
  college: 'none',
  group: 0,
  policies: 0,
  savings: 0,
})

export const blankSaved = (): SavedProfile => ({ p: blankProfile(), known: [], confirmed: false, updated: null })

export const MONEY_FIELDS = ['income', 'mortgage', 'otherDebt', 'group', 'policies', 'savings'] as const
export const INT_FIELDS = ['children', 'youngest', 'age', 'years', 'mortgageYears'] as const
export type NumberField = (typeof MONEY_FIELDS)[number] | (typeof INT_FIELDS)[number]
export const DEPS: Dep[] = ['partner', 'kids', 'relative', 'none']

export const LABEL: Record<Field, string> = {
  deps: 'Who relies on you',
  children: 'Children',
  youngest: "Youngest's age",
  age: 'Your age',
  income: 'Yearly income',
  years: 'Years of support',
  mortgage: 'Mortgage balance',
  mortgageYears: 'Years left on mortgage',
  otherDebt: 'Other debts',
  college: 'College',
  group: 'Coverage through work',
  policies: 'Policies you own',
  savings: 'Savings to count',
}

export const COLLEGE_LABEL: Record<College, string> = {
  public: 'Public in-state',
  half: 'About half',
  none: 'Not part of the plan',
}

export const hasDep = (p: Profile, d: Dep) => p.deps.includes(d)
export const hasKids = (p: Profile) => hasDep(p, 'kids')
const anyone = (p: Profile) => p.deps.length > 0 && !hasDep(p, 'none')
export const isMoney = (k: string): boolean => (MONEY_FIELDS as readonly string[]).includes(k)
export const isInt = (k: string): boolean => (INT_FIELDS as readonly string[]).includes(k)

export const depsText = (p: Profile): string =>
  hasDep(p, 'none')
    ? 'No one right now'
    : p.deps
        .map((d) => ({ partner: 'Partner', kids: 'Children', relative: 'A parent or relative', none: '' })[d])
        .join(', ') || '—'

export const showVal = (k: Field, p: Profile): string =>
  k === 'deps'
    ? depsText(p)
    : isMoney(k)
      ? fmt(p[k] as number)
      : k === 'college'
        ? COLLEGE_LABEL[p.college]
        : k === 'years' || k === 'mortgageYears'
          ? `${p[k]} yrs`
          : String(p[k])

export interface FlowStep {
  k: Field
  need?: (p: Profile) => boolean
  q: (p: Profile) => string
  chips?: (p: Profile) => string[]
}

/* Onboarding asks one field at a time, in this order, skipping steps whose `need` is false. */
export const FLOW: FlowStep[] = [
  {
    k: 'deps',
    q: () => 'First, who depends on your income? For example a partner, kids, or a parent.',
    chips: () => ['My partner', 'Partner and kids', 'Just my kids', 'A parent', 'No one'],
  },
  { k: 'children', need: hasKids, q: () => 'How many children do you have?', chips: () => ['1', '2', '3'] },
  { k: 'youngest', need: hasKids, q: () => 'How old is your youngest?' },
  { k: 'age', q: () => 'How old are you?' },
  {
    k: 'income',
    q: () => "What's your yearly income before taxes? A rough number is fine.",
    chips: () => ['$50k', '$75k', '$100k'],
  },
  {
    k: 'years',
    need: anyone,
    q: (p) =>
      hasKids(p)
        ? `How many years should your income keep supporting them? Many families choose until the youngest is 22, which is ${Math.max(5, 22 - p.youngest)} years.`
        : 'For how many years should your income keep supporting them?',
    chips: (p) => [...(hasKids(p) ? ['Until my youngest is 22'] : []), '10 years', '15 years', '20 years'],
  },
  {
    k: 'mortgage',
    q: () => 'Do you have a mortgage? If so, about how much is left on it?',
    chips: () => ['No mortgage'],
  },
  { k: 'mortgageYears', need: (p) => p.mortgage > 0, q: () => 'About how many years are left on it?' },
  {
    k: 'otherDebt',
    q: () => 'Any other debts, like car loans, student loans or cards? A total is fine.',
    chips: () => ['None'],
  },
  {
    k: 'college',
    need: hasKids,
    q: () => 'Should coverage help pay for college? Fully, about half, or not part of the plan?',
    chips: () => ['Yes, public in-state', 'About half', 'Not part of the plan'],
  },
  {
    k: 'group',
    q: () => "Do you have life insurance through work? If so, how much? It's often 1 or 2 times salary.",
    chips: () => ['None', '1x salary', '2x salary'],
  },
  {
    k: 'policies',
    q: () => 'Any life insurance policies you own yourself? If so, the total amount.',
    chips: () => ['None'],
  },
  {
    k: 'savings',
    q: () => "Last one: how much savings would you want counted toward your family's needs?",
    chips: () => ['None', '$10k', '$25k'],
  },
]

export const neededSteps = (saved: SavedProfile) => FLOW.filter((f) => !f.need || f.need(saved.p))
export const nextStep = (saved: SavedProfile) => neededSteps(saved).find((f) => !saved.known.includes(f.k))
