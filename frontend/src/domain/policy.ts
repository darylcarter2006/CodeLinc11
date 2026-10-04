import { POLICY_FIELDS, type Field, type PolicyField, type Profile, type SavedProfile } from './profile'

/*
 * Coverage type: a hidden tally over the five onboarding preferences. Each answer adds one
 * point to term or permanent; the higher score wins and a tie goes to term. Deterministic code,
 * mirrored in backend/app/domain/compass.py so the Chat tab can explain the same result.
 */

export type PolicyType = 'term' | 'perm'

/** Which side each answer counts toward. */
const SIDE: Record<PolicyField, Record<string, PolicyType>> = {
  coverFor: { period: 'term', lifelong: 'perm' },
  budget: { lowest: 'term', more: 'perm' },
  cashValue: { no: 'term', yes: 'perm' },
  legacy: { no: 'term', yes: 'perm' },
  simple: { yes: 'term', no: 'perm' },
}

/** One plain-language reason per answer, shown in the result pop-up. */
const REASON: Record<PolicyField, Record<string, string>> = {
  coverFor: {
    period: 'You want coverage for a specific period, like until the kids are grown.',
    lifelong: 'You want coverage that lasts your whole life.',
  },
  budget: {
    lowest: 'You want the most coverage for the lowest monthly cost.',
    more: "You're willing to pay more for added benefits.",
  },
  cashValue: {
    no: "You don't need the policy to build cash value.",
    yes: "You'd like the policy to build cash value you can use while you're alive.",
  },
  legacy: {
    no: 'Covering these needs is the goal, rather than leaving extra to heirs.',
    yes: 'You want to leave money to your heirs beyond these needs.',
  },
  simple: {
    yes: 'You prefer a simple policy that just pays out.',
    no: 'You want extra options, like cash value or flexible payments.',
  },
}

export interface PolicyReason {
  field: PolicyField
  text: string
  side: PolicyType
}

export interface PolicyFit {
  type: PolicyType
  term: number
  perm: number
  reasons: PolicyReason[]
}

/** Score the answers. With `known`, only answered questions count (a skipped one adds nothing). */
export function policyFit(p: Profile, known?: readonly Field[]): PolicyFit {
  const reasons: PolicyReason[] = []
  for (const field of POLICY_FIELDS) {
    if (known && !known.includes(field)) continue
    const side = SIDE[field][p[field]]
    if (side) reasons.push({ field, side, text: REASON[field][p[field]] })
  }
  const term = reasons.filter((r) => r.side === 'term').length
  const perm = reasons.length - term
  return { type: perm > term ? 'perm' : 'term', term, perm, reasons }
}

/** True once every coverage-type question has been answered. */
export const policyAnswered = (saved: SavedProfile) => POLICY_FIELDS.every((f) => saved.known.includes(f))

export const POLICY_TYPE: Record<PolicyType, { name: string; summary: string; points: string[] }> = {
  term: {
    name: 'Term life insurance',
    summary: 'Coverage for a set number of years, such as 20 or 30, chosen to match how long your family needs support.',
    points: [
      'Usually the lowest cost for the most coverage.',
      'Pays a death benefit only if you die during the term.',
      'Simple: no cash value or investment features.',
    ],
  },
  perm: {
    name: 'Permanent life insurance',
    summary: 'Coverage meant to last your whole life, such as whole or universal life.',
    points: [
      'Builds cash value you can use while you are alive.',
      'Can leave money to heirs, whenever you die.',
      'Costs more than term for the same death benefit.',
    ],
  },
}
