import { fmt } from './format'
import { compute, type Calculation } from './needs'
import type { Profile } from './profile'

/* One-sentence explanations of the key numbers, built from the person's own values. */

export const explainInPlace = (p: Profile, c: Calculation) =>
  `${fmt(p.group)} through work + ${fmt(p.policies)} in policies you own + ${fmt(p.savings)} in savings you counted = ${fmt(c.existing)}. That covers about ${c.total ? Math.round((c.existing / c.total) * 100) : 100}% of the estimated need.`

export const explainNeed = (c: Calculation) =>
  `${c.lines.map((l) => `${l.label} ${fmt(l.amt)}`).join(' + ')} = ${fmt(c.total)}. See the Breakdown tab for how each part is figured.`

export const explainLeft = (c: Calculation) =>
  c.gap === 0
    ? `What you have (${fmt(c.existing)}) already meets the estimated need (${fmt(c.total)}), so nothing is left to cover.`
    : `Estimated need ${fmt(c.total)} − coverage in place ${fmt(c.existing)} = ${fmt(c.gap)}. Rounded up to the nearest $25,000, that gives a starting point of ${fmt(c.suggested)}.`

export const explainTerm = (p: Profile, c: Calculation) => {
  const parts = [`${c.years} years of income support`]
  if (p.mortgage > 0) parts.push(`${p.mortgageYears} years left on the mortgage`)
  return `Your longest need is ${c.termNeed} years (${parts.join(', ')}). Term policies usually come in 10, 15, 20, 25 or 30 years, so this rounds up to ${c.term}.`
}

export const explainRange = (c: Calculation) =>
  `About 15% below and above the ${fmt(c.gap)} left to cover, rounded to $25,000 steps. It's a band rather than one number because this estimate doesn't model inflation, investment returns, taxes, or changes ahead like a raise or another child. It's an estimate, not a quote.`

/** The parts of the need that move the amount most, and what one change to their answers would do, all computed. */
export function explainDrivers(p: Profile, c: Calculation): string[] {
  const out = c.drivers
    .slice(0, 2)
    .map((d) => `${d.label} is ${d.share}% of your need (${fmt(d.amt)}), set by ${d.answers}.`)
  if (c.years > 0) {
    const more = compute({ ...p, years: c.years + 1 })
    out.push(`One more year of income support would add ${fmt(more.suggested - c.suggested)} to the starting point.`)
  }
  if (c.years > 0 && p.income > 0) {
    const raise = compute({ ...p, income: p.income + 10000 })
    out.push(`$10,000 more yearly income would add ${fmt(raise.suggested - c.suggested)}.`)
  }
  return out
}
