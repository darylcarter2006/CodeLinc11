import { NavLink, Outlet } from 'react-router-dom'
import { useSession } from '../session/context'

export function Layout() {
  const { error, clearError, startOver, busy, status } = useSession()

  return (
    <div className="app-shell">
      <header className="app-header">
        <NavLink to="/" className="brand">
          Coverage Needs Analyzer
        </NavLink>
        <nav>
          <NavLink to="/planner">Planner</NavLink>
          <NavLink to="/profile">My answers</NavLink>
          <NavLink to="/learn">Learn</NavLink>
        </nav>
        <button
          type="button"
          className="secondary"
          disabled={busy || status !== 'ready'}
          onClick={() => {
            if (confirm('Start over? This deletes your answers from this session.')) void startOver()
          }}
        >
          Start over
        </button>
      </header>

      {error && (
        <div className="banner error" role="alert">
          <span>{error}</span>
          <button type="button" className="link-button" onClick={clearError}>
            Dismiss
          </button>
        </div>
      )}

      <main className="app-main">
        <Outlet />
      </main>

      <footer className="app-footer muted small">
        Planning estimate only, not a quote, underwriting decision, or product recommendation. All amounts are estimates
        you entered.
      </footer>
    </div>
  )
}
