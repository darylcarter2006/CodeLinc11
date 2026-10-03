import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { CoverageTypesResponse } from '../api/types'

export function LearnPage() {
  const [content, setContent] = useState<CoverageTypesResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.coverageTypes().then(setContent, (e: Error) => setError(e.message))
  }, [])

  if (error) return <p className="error-text">{error}</p>
  if (!content) return <p className="muted">Loading…</p>

  return (
    <div className="learn">
      <h1>Types of life insurance</h1>
      <div className="card-grid">
        {content.coverage_types.map((t) => (
          <article key={t.id} className="panel">
            <h2>{t.title}</h2>
            <p>{t.summary}</p>
            <ul>
              {t.points.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </article>
        ))}
      </div>
      {content.resources.length > 0 && (
        <section>
          <h2>Resources</h2>
          <ul>
            {content.resources.map((r) => (
              <li key={r.url}>
                <a href={r.url} target="_blank" rel="noreferrer">
                  {r.title}
                </a>{' '}
                ({r.source_owner}): {r.summary}
              </li>
            ))}
          </ul>
        </section>
      )}
      <p className="disclaimer">{content.disclaimer}</p>
    </div>
  )
}
