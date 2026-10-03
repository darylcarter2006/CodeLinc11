import type { AssessmentPreview, AssessmentStatus } from '../api/types'
import { useSession } from '../session/context'
import { fieldLabel, formatMoney } from '../utils/format'

const STATUS_COPY: Record<AssessmentStatus, { label: string; detail: string }> = {
  incomplete: { label: 'Not enough info yet', detail: 'Answer the remaining questions to see an estimate.' },
  partial: { label: 'Preliminary', detail: 'Some answers are unconfirmed or unknown and were counted as $0.' },
  complete: { label: 'Complete', detail: 'Every answer used here is known and confirmed by you.' },
}

/**
 * Shows the server's live estimate. Every line item is rendered with its full amount so the
 * total can be checked by hand: rows 1-5 always add up to the gap.
 */
export function AssessmentPanel({ assessment }: { assessment: AssessmentPreview }) {
  const { busy, saveAssessment, savedAssessment, state } = useSession()
  const status = STATUS_COPY[assessment.status]
  const items = [...assessment.line_items].sort((a, b) => a.display_order - b.display_order)
  const savedIsCurrent = savedAssessment && savedAssessment.profile_revision === state?.revision

  return (
    <section className="panel assessment-panel" aria-label="Coverage estimate">
      <header className="assessment-header">
        <h2>Your estimate</h2>
        <span className={`status-badge status-${assessment.status}`}>{status.label}</span>
      </header>
      <p className="muted">{status.detail}</p>

      {assessment.status === 'incomplete' ? (
        <div>
          <p>Still needed:</p>
          <ul>
            {assessment.missing_fields.map((f) => (
              <li key={f}>{fieldLabel(f)}</li>
            ))}
          </ul>
        </div>
      ) : (
        <>
          <div className="gap-total">
            <span>Additional coverage gap</span>
            <strong>{formatMoney(assessment.additional_coverage_gap ?? 0)}</strong>
          </div>
          {assessment.annual_shortfall !== null && assessment.support_years !== null && (
            <p className="muted small">
              Based on an annual shortfall of {formatMoney(assessment.annual_shortfall)} for {assessment.support_years}{' '}
              years.
            </p>
          )}

          <table className="line-items">
            <caption className="sr-only">How the estimate is calculated</caption>
            <tbody>
              {items.map((item) => (
                <tr key={item.code} className={item.code === 'additional_gap' ? 'total-row' : undefined}>
                  <th scope="row">
                    {item.label}
                    {item.entered_amount !== null && item.entered_amount !== -item.amount && (
                      <div className="muted small">
                        You entered {formatMoney(item.entered_amount)}; only {formatMoney(-item.amount)} was needed.
                      </div>
                    )}
                  </th>
                  <td>{formatMoney(item.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {assessment.explanation && <p>{assessment.explanation}</p>}

      {assessment.warnings.length > 0 && (
        <div className="callout warning">
          <strong>Check these</strong>
          <ul>
            {assessment.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {assessment.assumptions.length > 0 && (
        <details>
          <summary>Assumptions used ({assessment.assumptions.length})</summary>
          <ul>
            {assessment.assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </details>
      )}

      {assessment.limitations.length > 0 && (
        <details>
          <summary>What this estimate doesn't cover</summary>
          <ul>
            {assessment.limitations.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </details>
      )}

      {assessment.status !== 'incomplete' && (
        <div className="button-row">
          <button type="button" disabled={busy || !!savedIsCurrent} onClick={() => void saveAssessment()}>
            {savedIsCurrent ? 'Saved' : 'Save this estimate'}
          </button>
          {savedAssessment && !savedIsCurrent && (
            <span className="muted small">Your answers changed since the last save.</span>
          )}
        </div>
      )}

      <p className="disclaimer">{assessment.disclaimer}</p>
      <p className="muted small">Calculation version {assessment.calculation_version}</p>
    </section>
  )
}
