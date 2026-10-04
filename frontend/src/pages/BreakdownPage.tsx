import { Link, useNavigate } from 'react-router-dom'
import { Legend, StackedBar } from '../components/StackedBar'
import { NumberInfo, WithTerms } from '../components/Tip'
import { TradeoffCards } from '../components/TradeoffCard'
import { explainDrivers, explainInPlace, explainLeft, explainNeed, explainRange, explainTerm } from '../domain/explain'
import { fmt, short } from '../domain/format'
import { compute, tradeoffs, type Calculation } from '../domain/needs'
import type { Profile } from '../domain/profile'
import { useApp } from '../state/context'

/* Breakdown: the headline starting point, every line of the math with "Why?", and tradeoffs. */
export function BreakdownPage() {
  const { profile: p, isExample } = useApp()
  const navigate = useNavigate()
  const c = compute(p)
  const why = (label: string) => navigate('/chat', { state: { ask: `Why is “${label}” in my estimate, and how was it calculated?` } })

  return (
    <>
      <div className="view-head">
        <div>
          <div className="eyebrow">{isExample ? 'Example breakdown' : 'Breakdown'}</div>
          <h2>How we got your number</h2>
        </div>
        <Link className="btn ghost" to="/info">
          Edit my info
        </Link>
      </div>
      <div className="results">
        <Headline p={p} c={c} isExample={isExample} />

        <div className="card pad">
          <div className="sec-head">
            <h2>How we got here</h2>
            <span className="muted small">Needs-based method</span>
          </div>
          <div className="chart" role="img" aria-label={`Total need ${fmt(c.total)}; already in place ${fmt(c.existing)}; left to cover ${fmt(c.gap)}`}>
            <div>
              <div className="row-lbl">
                <span>What the need is made of</span>
                <span className="num">{fmt(c.total)}</span>
              </div>
              <StackedBar
                total={c.total}
                segments={c.lines.map((l) => ({ key: l.key, tone: l.key, amount: l.amt, tip: `${l.label}: ${fmt(l.amt)}` }))}
              />
              <Legend
                items={c.lines
                  .filter((l) => l.amt > 0)
                  .map((l) => ({ key: l.key, color: `var(--${l.key})`, label: l.label, value: short(l.amt) }))}
              />
            </div>
            <div>
              <div className="row-lbl">
                <span>How it's covered</span>
                <span className="num">{fmt(c.total)}</span>
              </div>
              <StackedBar
                total={c.total}
                segments={[
                  { key: 'have', tone: 'have', amount: Math.min(c.existing, c.total), tip: `Already in place: ${fmt(c.existing)}` },
                  { key: 'left', tone: 'left', amount: c.gap, tip: `Left to cover: ${fmt(c.gap)}` },
                ]}
              />
              <Legend
                items={[
                  { key: 'have', color: 'var(--teal)', label: 'Already in place', value: short(c.existing) },
                  { key: 'left', color: 'var(--orange)', label: 'Left to cover', value: short(c.gap) },
                ]}
              />
            </div>
          </div>

          <div className="tbl-wrap">
            <table>
              <thead>
                <tr>
                  <th>Item and how we figured it</th>
                  <th className="amt">Amount</th>
                </tr>
              </thead>
              <tbody>
                {c.lines.map((l) => (
                  <tr key={l.key}>
                    <td>
                      <span className="sw" style={{ background: `var(--${l.key})` }} />
                      <WithTerms text={l.label} />
                      <div className="how">{l.how}</div>
                      <button className="why-btn" type="button" onClick={() => why(l.label)}>
                        Why?
                      </button>
                    </td>
                    <td className="amt">{fmt(l.amt)}</td>
                  </tr>
                ))}
                <tr className="total">
                  <td>Total need</td>
                  <td className="amt">{fmt(c.total)}</td>
                </tr>
                <tr className="sub">
                  <td>
                    Minus what's already in place
                    <div className="how">
                      {fmt(p.group)} work + {fmt(p.policies)} personal + {fmt(p.savings)} savings
                    </div>
                  </td>
                  <td className="amt">− {fmt(c.existing)}</td>
                </tr>
                <tr className="total">
                  <td>
                    Left to cover
                    <div className="how plain">Rounded up to the nearest $25,000: {fmt(c.suggested)}</div>
                  </td>
                  <td className="amt accent">{fmt(c.gap)}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div className="note orange spaced">
            <b>Assumptions.</b> We replace 75% of income because some of it currently goes to your own costs and taxes.
            College is about $100,000 per child for a public in-state school. Final expenses are $15,000. Figures are in
            today's dollars and don't include inflation or investment growth.
          </div>
        </div>

        <div className="card pad">
          <div className="sec-head">
            <h2>Tradeoffs for your situation</h2>
            <span className="muted small">Based on your answers</span>
          </div>
          <TradeoffCards items={tradeoffs(p, c)} />
        </div>
      </div>
    </>
  )
}

function Headline({ p, c, isExample }: { p: Profile; c: Calculation; isExample: boolean }) {
  if (c.gap === 0)
    return (
      <div className="card pad">
        <div className="eyebrow">Good news</div>
        <h2 className="covered-title">What you have already covers this estimate</h2>
        <p className="muted">
          Your existing coverage and savings ({fmt(c.existing)}) meet the estimated need of {fmt(c.total)}. Revisit this
          after big life changes.
        </p>
        <p className="estimate-note">An estimate from your answers, not financial advice or a quote.</p>
      </div>
    )
  return (
    <div className="card pad">
      <div className="hero">
        <div>
          <div className="eyebrow">{isExample ? 'Example result · ' : ''}A reasonable starting point</div>
          <div className="figure" data-testid="suggested">
            {fmt(c.suggested)} <NumberInfo label="the starting point" explanation={explainLeft(c)} testId="info-suggested" />
          </div>
          <div className="muted small">
            Estimate range{' '}
            <b className="num ink">
              {fmt(c.low)} – {fmt(c.high)}
            </b>
            <NumberInfo label="the range" explanation={explainRange(c)} testId="info-range" />
          </div>
          <p className="estimate-note" data-testid="estimate-note">
            An estimate from your answers, not financial advice or a quote. It's a range because it doesn't model
            inflation, investment returns, taxes, or changes ahead.
          </p>
        </div>
        <div className="facts">
          <span>
            Term that matches your needs <b>{c.term} years</b> <NumberInfo label="the matching term" explanation={explainTerm(p, c)} testId="info-term" />
          </span>
          <span>
            Total need <b>{fmt(c.total)}</b> <NumberInfo label="the total need" explanation={explainNeed(c)} testId="info-total" />
          </span>
          <span>
            Already in place <b>{fmt(c.existing)}</b> <NumberInfo label="what's already in place" explanation={explainInPlace(p, c)} testId="info-existing" />
          </span>
        </div>
      </div>
      {c.drivers.length > 0 && (
        <div className="drivers spaced" data-testid="drivers">
          <h3>What moves your amount most</h3>
          <ul>
            {explainDrivers(p, c).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      )}
      <div className="note teal spaced">
        <strong>You're not starting from zero.</strong> What you already have covers about{' '}
        {Math.round((c.existing / c.total) * 100)}% of the need. This estimate is a starting point you can adjust, not a
        verdict.
      </div>
    </div>
  )
}
