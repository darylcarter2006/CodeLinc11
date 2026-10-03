import { useState } from 'react'

export interface Segment {
  key: string
  /** CSS class that sets the color, e.g. "c1" or "have". */
  tone: string
  amount: number
  tip: string
}

interface Props {
  segments: Segment[]
  /** Width of 100%. Bars that share a scale pass the same total. */
  total: number
  variant?: 'track' | 'meter'
  label?: string
}

/** Horizontal stacked bar with hover tooltips. Always paired with a direct-labeled legend or table. */
export function StackedBar({ segments, total, variant = 'track', label }: Props) {
  const [tip, setTip] = useState<{ text: string; x: number; y: number } | null>(null)
  return (
    <>
      <div className={variant} role={label ? 'img' : undefined} aria-label={label}>
        {segments
          .filter((s) => s.amount > 0)
          .map((s) => (
            <span
              key={s.key}
              className={`seg ${s.tone}`}
              style={{ width: `${((s.amount / total) * 100).toFixed(3)}%` }}
              onMouseMove={(e) => setTip({ text: s.tip, x: e.clientX + 12, y: e.clientY - 34 })}
              onMouseLeave={() => setTip(null)}
            />
          ))}
      </div>
      {tip && (
        <div className="tip" style={{ left: tip.x, top: tip.y }} aria-hidden>
          {tip.text}
        </div>
      )}
    </>
  )
}

export function Legend({ items }: { items: { key: string; color: string; label: string; value: string }[] }) {
  return (
    <div className="legend">
      {items.map((i) => (
        <span key={i.key}>
          <i style={{ background: i.color }} />
          {i.label} <b className="num">{i.value}</b>
        </span>
      ))}
    </div>
  )
}
