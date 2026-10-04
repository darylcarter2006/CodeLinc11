import { fmt, short } from '../domain/format'
import { compute } from '../domain/needs'
import type { Profile } from '../domain/profile'

/* Canned, keyword-matched answers for the Chat tab when live AI is unavailable. */

const FALLBACK: [RegExp, (p: Profile) => string][] = [
  [
    /job|work|employer|hr/i,
    (p) =>
      `Coverage through work usually ends when you leave the job. ${p.group ? `Without the ${short(p.group)} from work, the starting point would rise to ${fmt(compute({ ...p, group: 0 }).suggested)}.` : ''} Some plans let you convert it to an individual policy, so it's worth asking HR.`,
  ],
  [
    /term|whole/i,
    () =>
      'Term life covers a set number of years at a lower cost. Whole life lasts your lifetime and builds cash value, but costs much more for the same amount. When most of a need fades over time, many people look at term first. A licensed professional can help you weigh both.',
  ],
  [
    /enough|compare with the estimate/i,
    (p) => {
      const c = compute(p)
      return `You have ${fmt(c.existing)} in place against an estimated need of ${fmt(c.total)}, about ${Math.round((c.existing / c.total) * 100)}% of it. The estimate's starting point for added coverage is ${fmt(c.suggested)}.`
    },
  ],
  [/saving/i, () => "Counting savings lowers the coverage you need, but that money then can't also be your emergency fund or retirement savings."],
  [
    /two|split|ladder/i,
    () =>
      'Laddering means buying two policies that end at different times, so coverage steps down as your needs shrink. It can lower total cost compared with one large, long policy.',
  ],
  [
    /75|income/i,
    () =>
      "Some of your income goes to your own costs and taxes, which stop if you're gone. Replacing about 75% keeps your family's lifestyle close to what it is today.",
  ],
]

const DEFAULT = 'Every number in your estimate is listed with its formula on the Breakdown tab. To change an answer, use My info.'

export const fallbackAnswer = (question: string, p: Profile): string =>
  (FALLBACK.find(([re]) => re.test(question))?.[1] ?? (() => DEFAULT))(p)
