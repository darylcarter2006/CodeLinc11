import type { Tradeoff } from '../domain/needs'
import { WithTerms } from './Tip'

export function TradeoffCards({ items, withPairs = true }: { items: Tradeoff[]; withPairs?: boolean }) {
  return (
    <div className="trades">
      {items.map((t) => (
        <article key={t.tag} className="trade">
          <span className="eyebrow">{t.tag}</span>
          <h3>{t.title}</h3>
          <p>
            <WithTerms text={t.body} />
          </p>
          {withPairs && t.pair && (
            <div className="pair">
              {t.pair.map(([h, b]) => (
                <div key={h}>
                  <b>{h}</b>
                  <WithTerms text={b} />
                </div>
              ))}
            </div>
          )}
        </article>
      ))}
    </div>
  )
}
