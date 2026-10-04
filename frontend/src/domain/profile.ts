import { fmt } from './format'

/* Profile model and the field catalog: labels, display values, and the onboarding question order. */

export type Dep = 'partner' | 'kids' | 'relative' | 'none'
export type College = 'public' | 'half' | 'none'
/* Coverage-type preferences: asked during onboarding and scored in domain/policy.ts. */
export type CoverFor = 'period' | 'lifelong'
export type Budget = 'lowest' | 'more'
export type YesNo = 'yes' | 'no'

export interface Profile {
  deps: Dep[]
  children: number
  youngest: number
  income: number
  years: number
  mortgage: number
  mortgageYears: number
  otherDebt: number
  college: College
  group: number
  policies: number
  savings: number
  /** What they could comfortably spend on coverage each month; 0 means not sure. */
  monthlyBudget: number
  coverFor: CoverFor
  budget: Budget
  cashValue: YesNo
  legacy: YesNo
  simple: YesNo
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
  income: 78000,
  years: 19,
  mortgage: 240000,
  mortgageYears: 26,
  otherDebt: 18000,
  college: 'public',
  group: 156000,
  policies: 0,
  savings: 20000,
  monthlyBudget: 60,
  coverFor: 'period',
  budget: 'lowest',
  cashValue: 'no',
  legacy: 'no',
  simple: 'yes',
}

export const blankProfile = (): Profile => ({
  deps: [],
  children: 0,
  youngest: 0,
  income: 0,
  years: 0,
  mortgage: 0,
  mortgageYears: 0,
  otherDebt: 0,
  college: 'none',
  group: 0,
  policies: 0,
  savings: 0,
  monthlyBudget: 0,
  coverFor: 'period',
  budget: 'lowest',
  cashValue: 'no',
  legacy: 'no',
  simple: 'yes',
})

export const blankSaved = (): SavedProfile => ({ p: blankProfile(), known: [], confirmed: false, updated: null })

export const MONEY_FIELDS = ['income', 'mortgage', 'otherDebt', 'group', 'policies', 'savings', 'monthlyBudget'] as const
export const INT_FIELDS = ['children', 'youngest', 'years', 'mortgageYears'] as const
export type NumberField = (typeof MONEY_FIELDS)[number] | (typeof INT_FIELDS)[number]
export const DEPS: Dep[] = ['partner', 'kids', 'relative', 'none']
export const POLICY_FIELDS = ['coverFor', 'budget', 'cashValue', 'legacy', 'simple'] as const
export type PolicyField = (typeof POLICY_FIELDS)[number]
export const isPolicyField = (k: string): k is PolicyField => (POLICY_FIELDS as readonly string[]).includes(k)

/** The answer choices for each coverage-type question; also the onboarding quick replies. */
export const POLICY_CHOICES: Record<PolicyField, Record<string, string>> = {
  coverFor: { period: 'A specific period', lifelong: 'My whole life' },
  budget: { lowest: 'Lowest monthly cost', more: 'Willing to pay more' },
  cashValue: { no: 'No', yes: 'Yes' },
  legacy: { no: 'No', yes: 'Yes' },
  simple: { yes: 'Keep it simple', no: 'I want extra options' },
}

export const LABEL: Record<Field, string> = {
  deps: 'Who relies on you',
  children: 'Children',
  youngest: "Youngest's age",
  income: 'Yearly income',
  years: 'Years of support',
  mortgage: 'Mortgage balance',
  mortgageYears: 'Years left on mortgage',
  otherDebt: 'Other debts',
  college: 'College',
  group: 'Coverage through work',
  policies: 'Policies you own',
  savings: 'Savings to count',
  monthlyBudget: 'Comfortable monthly budget',
  coverFor: 'How long you want coverage',
  budget: 'Cost or added benefits',
  cashValue: 'Build cash value',
  legacy: 'Leave money to heirs',
  simple: 'Prefer a simpler policy',
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

export const showVal = (k: Field, p: Profile): string => {
  if (isPolicyField(k)) return POLICY_CHOICES[k][p[k]]
  if (k === 'deps') return depsText(p)
  if (k === 'monthlyBudget') return p.monthlyBudget ? `${fmt(p.monthlyBudget)} a month` : 'Not sure'
  if (isMoney(k)) return fmt(p[k] as number)
  if (k === 'college') return COLLEGE_LABEL[p.college]
  if (k === 'years' || k === 'mortgageYears') return `${p[k]} yrs`
  return String(p[k])
}

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
    q: () => "How much savings would you want counted toward your family's needs?",
    chips: () => ['None', '$10k', '$25k'],
  },
  {
    k: 'monthlyBudget',
    q: () => "What could you comfortably spend each month on life insurance? A rough number is fine, or say you're not sure.",
    chips: () => ['$25', '$50', '$100', 'Not sure'],
  },
  // Coverage-type questions. Each answer adds a point to term or permanent (domain/policy.ts);
  // the tally isn't shown while they answer.
  {
    k: 'coverFor',
    q: () =>
      'A few quick questions about the kind of coverage that suits you. Do you want coverage for a specific period, like until the kids are grown or the mortgage is paid off, or for your whole life?',
    chips: () => Object.values(POLICY_CHOICES.coverFor),
  },
  {
    k: 'budget',
    q: () => 'Is getting the most coverage for the lowest monthly cost the priority, or would you pay more for added benefits?',
    chips: () => Object.values(POLICY_CHOICES.budget),
  },
  {
    k: 'cashValue',
    q: () => "Would you like the policy to build cash value you could use while you're alive?",
    chips: () => Object.values(POLICY_CHOICES.cashValue),
  },
  {
    k: 'legacy',
    q: () => 'Do you want to leave money to your heirs beyond covering these needs?',
    chips: () => Object.values(POLICY_CHOICES.legacy),
  },
  {
    k: 'simple',
    q: () =>
      'Last one: would you prefer a simple policy that just pays out if you die, or one with extra options, like cash value or flexible payments?',
    chips: () => Object.values(POLICY_CHOICES.simple),
  },
]

export const neededSteps = (saved: SavedProfile) => FLOW.filter((f) => !f.need || f.need(saved.p))
export const nextStep = (saved: SavedProfile) => neededSteps(saved).find((f) => !saved.known.includes(f.k))
