import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { areaFor, useApp } from '../state/context'
import { AccessibilityMenu } from './AccessibilityMenu'

const TABS = [
  ['/dashboard', 'Dashboard'],
  ['/breakdown', 'Breakdown'],
  ['/info', 'My info'],
  ['/chat', 'Chat'],
] as const

/* Navy top bar (Lincoln Financial mark, wordmark, tabs, account button), the page, and the standing footer note. */
export function Layout() {
  const state = useApp()
  const navigate = useNavigate()
  const area = areaFor(state)

  const onLeave = () => {
    const wasExample = state.isExample
    state.leave()
    if (!wasExample) navigate('/auth', { state: { mode: 'login' } })
  }

  return (
    <>
      <div className="topbar">
        <header>
          <div className="mark">
            {/* Official Lincoln Financial portrait mark, shown unaltered (no recoloring or stretching). */}
            <img className="logo" src="/icon-192.png" width={44} height={44} alt="Lincoln Financial" />
            <div>
              <h1>Coverage Compass</h1>
              <span className="tag">Life insurance needs analyzer from Lincoln Financial</span>
            </div>
          </div>
          <div className="hdr-right">
            <AccessibilityMenu />
            {area === 'app' && (
              <nav className="tabs" aria-label="Sections">
                {TABS.map(([to, label]) => (
                  <NavLink key={to} to={to} className="tab">
                    {label}
                  </NavLink>
                ))}
              </nav>
            )}
            {area !== 'auth' && (
              <button className="acct" type="button" onClick={onLeave}>
                <span className="avatar" aria-hidden>
                  {state.isExample ? 'E' : (state.account?.name || '?')[0].toUpperCase()}
                </span>
                <span>{state.isExample ? 'Exit example' : 'Sign out'}</span>
              </button>
            )}
          </div>
        </header>
      </div>
      <div className="wrap">
        <main>
          {state.saveFailed && (
            <p className="save-banner" role="status">
              Your latest changes haven't been saved to your account yet. We'll keep trying; check your connection.
            </p>
          )}
          <Outlet />
        </main>
        <footer>
          Coverage Compass is an educational concept built for the codeLinc 11 coding challenge. Estimates use simple,
          stated assumptions and are not financial advice or a quote. A licensed professional can help confirm what fits
          you.
        </footer>
      </div>
    </>
  )
}
