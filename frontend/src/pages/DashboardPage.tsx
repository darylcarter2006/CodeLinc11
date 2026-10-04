import { Link } from 'react-router-dom'
import { Legend, StackedBar } from '../components/StackedBar'
import { NumberInfo, WithTerms } from '../components/Tip'
import { TradeoffCards } from '../components/TradeoffCard'
import { explainInPlace, explainLeft, explainNeed, explainTerm } from '../domain/explain'
import { fmt, short, shortDate } from '../domain/format'
import { compute, coveredPct, nextSteps, tradeoffs } from '../domain/needs'
import { EXAMPLE_NAME, depsText, hasKids } from '../domain/profile'
import { useApp } from '../state/context'

const lineColor = (key: string) => `var(--${key})`

/* Dashboard: tiles, coverage sources, what the need is made of, tradeoffs, next steps, situation. */
export function DashboardPage() {
  const { profile: p, isExample, account, saved, steps, toggleStep } = useApp()
  const c = compute(p)
  const pct = coveredPct(c)
  const parts = c.lines.filter((l) => l.amt > 0)
  const sources: [string, number, [string, string], string][] = [
    ['Coverage through work', p.group, p.group ? ['warn', 'Tied to your job'] : ['', 'None'], 'Group life from your employer. It usually ends if you change jobs.'],
    ['Policies you own', p.policies, p.policies ? ['ok', 'Stays with you'] : ['', 'None yet'], 'Individual term or permanent policies in your name.'],
    ['Savings you counted', p.savings, p.savings ? ['', 'Counted'] : ['', 'Not counted'], 'Money your family could use. It also has other jobs, like emergencies.'],
  ]

  return (
    <>
      <div className="view-head">
        <div>
          <div className="eyebrow">{isExample ? 'Example dashboard' : `Welcome back, ${account?.name}`}</div>
          <h2>Your coverage at a glance</h2>
          {!isExample && saved.updated && <div className="muted small">Last updated {shortDate(saved.updated, true)}</div>}
        </div>
        <div className="actions">
          <Link className="btn" to="/info">
            Edit my info
          </Link>
          <Link className="btn ghost" to="/chat">
            Ask about my coverage
          </Link>
        </div>
      </div>

      {isExample && (
        <div className="ex-note">
          <b>You're viewing an example</b> for {EXAMPLE_NAME}, 34. Exit the example and create an account to see your own
          coverage.
        </div>
      )}

      <div className="tiles">
        <Tile tone="have" k="Coverage in place" v={short(c.existing)} s={`${pct}% of the estimated need`} info={explainInPlace(p, c)} />
        <Tile tone="need" k="Estimated need" v={short(c.total)} s="Income, debts, college, final costs" info={explainNeed(c)} />
        <Tile tone="left" k="Left to cover" v={short(c.gap)} s={`Starting point ${short(c.suggested)}`} info={explainLeft(c)} />
        <Tile tone="term" k="Term that matches your needs" v={`${c.term} yrs`} s={`Matches your longest need (${c.termNeed} yrs)`} info={explainTerm(p, c)} />
      </div>

      <div className="dash">
        <div className="col">
          <div className="card pad">
            <div className="sec-head">
              <h2>Your coverage today</h2>
              <span className="muted num small">
                {fmt(c.existing)} of {fmt(c.total)}
              </span>
            </div>
            <StackedBar
              variant="meter"
              total={c.total}
              label={`${pct}% of the estimated need is covered`}
              segments={[
                { key: 'have', tone: 'have', amount: Math.min(c.existing, c.total), tip: `In place: ${fmt(c.existing)}` },
                { key: 'left', tone: 'left', amount: c.gap, tip: `Left to cover: ${fmt(c.gap)}` },
              ]}
            />
            <Legend
              items={[
                { key: 'have', color: 'var(--teal)', label: 'In place', value: short(c.existing) },
                { key: 'left', color: 'var(--orange)', label: 'Left to cover', value: short(c.gap) },
              ]}
            />
            <div className="src-list">
              {sources.map(([name, amt, [tone, pill], detail]) => (
                <div key={name} className="src">
                  <span className="nm">{name}</span>
                  <span className="amt">{fmt(amt)}</span>
                  <span className="dt">
                    <span className={`pill ${tone}`}>{pill}</span>
                    <span>
                      <WithTerms text={detail} />
                    </span>
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="card pad">
            <div className="sec-head">
              <h2>What the need is made of</h2>
              <Link className="linkish" to="/breakdown">
                See the math
              </Link>
            </div>
            <StackedBar
              total={c.total}
              label={parts.map((l) => `${l.label} ${fmt(l.amt)}`).join('; ')}
              segments={parts.map((l) => ({ key: l.key, tone: l.key, amount: l.amt, tip: `${l.label}: ${fmt(l.amt)}` }))}
            />
            <Legend items={parts.map((l) => ({ key: l.key, color: lineColor(l.key), label: l.label, value: short(l.amt) }))} />
          </div>

          <div className="card pad">
            <div className="sec-head">
              <h2>Tradeoffs to weigh</h2>
              <Link className="linkish" to="/breakdown">
                See all
              </Link>
            </div>
            <TradeoffCards items={tradeoffs(p, c).slice(0, 2)} withPairs={false} />
          </div>
        </div>

        <div className="col">
          <div className="card pad">
            <div className="sec-head">
              <h2>Next steps</h2>
            </div>
            <ul className="steps">
              {nextSteps(p, c).map((t) => (
                <li key={t}>
                  <label>
                    <input type="checkbox" checked={!!steps[t]} onChange={(e) => toggleStep(t, e.target.checked)} />
                    <span>{t}</span>
                  </label>
                </li>
              ))}
            </ul>
          </div>

          <div className="card pad">
            <div className="sec-head">
              <h2>Your situation</h2>
              <Link className="linkish" to="/info">
                Edit
              </Link>
            </div>
            <dl className="kv">
              <dt>Who relies on you</dt>
              <dd>{depsText(p)}</dd>
              {hasKids(p) && (
                <>
                  <dt>Children</dt>
                  <dd>
                    {p.children}, youngest {p.youngest}
                  </dd>
                </>
              )}
              <dt>Yearly income</dt>
              <dd>{fmt(p.income)}</dd>
              <dt>Years of support</dt>
              <dd>
                {c.years}
                {c.years > c.yearsEntered && <div className="muted small">until your youngest turns 18 (you entered {c.yearsEntered})</div>}
              </dd>
              <dt>Mortgage</dt>
              <dd>
                {fmt(p.mortgage)}
                {p.mortgage ? ` · ${p.mortgageYears} yrs left` : ''}
              </dd>
              <dt>Other debts</dt>
              <dd>{fmt(p.otherDebt)}</dd>
            </dl>
          </div>

          <div className="note teal">
            This dashboard is an educational estimate built from your answers. It isn't a quote or a record of your actual
            policies.
          </div>
        </div>
      </div>
    </>
  )
}

function Tile({ tone, k, v, s, info }: { tone: string; k: string; v: string; s: string; info: string }) {
  return (
    <div className={`card tile ${tone}`} data-testid={`tile-${tone}`}>
      <div className="k">
        {k} <NumberInfo label={k.toLowerCase()} explanation={info} testId={`info-${tone}`} />
      </div>
      <div className="v">{v}</div>
      <div className="s">{s}</div>
    </div>
  )
}
