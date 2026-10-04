/* Plain-language definitions for insurance terms, and a helper that finds them in UI text. */

export interface GlossaryEntry {
  term: string
  definition: string
  /** Phrases in UI text that should show this definition. Matched case-insensitively, whole words. */
  matches: string[]
}

export const GLOSSARY: Record<string, GlossaryEntry> = {
  term: {
    term: 'Term life insurance',
    definition:
      'Coverage for a set number of years, such as 20 or 30. It pays a death benefit if you die during that time. If the term ends first, coverage stops and nothing is paid.',
    matches: ['term life', 'term policy', 'term policies'],
  },
  whole: {
    term: 'Whole life insurance',
    definition:
      'A type of permanent insurance that lasts your whole life as long as you pay for it, and builds cash value. It usually costs much more than term for the same death benefit.',
    matches: ['whole life'],
  },
  permanent: {
    term: 'Permanent life insurance',
    definition: 'Coverage meant to last your whole life, usually with cash value. Whole life is the most common kind.',
    matches: ['permanent'],
  },
  cashValue: {
    term: 'Cash value',
    definition:
      'A savings-like part of permanent insurance that grows over time. You may be able to borrow or withdraw it, which can lower what the policy pays out.',
    matches: ['cash value'],
  },
  deathBenefit: {
    term: 'Death benefit',
    definition: 'The amount a life insurance policy pays to the people you name when you die.',
    matches: ['death benefit'],
  },
  beneficiary: {
    term: 'Beneficiary',
    definition: 'A person you name on a policy to receive the death benefit. Keep these up to date after life changes.',
    matches: ['beneficiary', 'beneficiaries'],
  },
  laddering: {
    term: 'Laddering',
    definition:
      'Owning two or more term policies that end at different times, so total coverage steps down as needs like a mortgage or raising children shrink.',
    matches: ['laddering', 'laddered'],
  },
  groupLife: {
    term: 'Group life insurance',
    definition:
      "Life insurance you get through an employer, often 1 or 2 times your salary. It usually ends when you leave the job, though some plans let you convert it to your own policy.",
    matches: ['group life'],
  },
  incomeReplacement: {
    term: 'Income replacement',
    definition:
      'Money to replace the paychecks your family would lose. This estimate uses 75% of your income, because part of it goes to your own costs and taxes.',
    matches: ['income replacement'],
  },
  finalExpenses: {
    term: 'Final expenses',
    definition: 'End-of-life costs such as a funeral, burial and settling your affairs. This estimate uses $15,000.',
    matches: ['final expenses'],
  },
}

export type TextPart = string | { key: string; text: string }

const escape = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

// Longest phrases first so "term life" wins over shorter overlaps.
const PHRASES = Object.entries(GLOSSARY)
  .flatMap(([key, e]) => e.matches.map((m) => ({ key, m })))
  .sort((a, b) => b.m.length - a.m.length)
const PATTERN = new RegExp(`\\b(${PHRASES.map((x) => escape(x.m)).join('|')})\\b`, 'gi')

/** Split text into plain strings and glossary terms. Each term is marked only the first time it appears. */
export function findTerms(text: string): TextPart[] {
  const parts: TextPart[] = []
  const seen = new Set<string>()
  let last = 0
  for (const match of text.matchAll(PATTERN)) {
    const key = PHRASES.find((x) => x.m === match[0].toLowerCase())!.key
    if (seen.has(key)) continue
    seen.add(key)
    if (match.index > last) parts.push(text.slice(last, match.index))
    parts.push({ key, text: match[0] })
    last = match.index + match[0].length
  }
  if (last < text.length) parts.push(text.slice(last))
  return parts
}
