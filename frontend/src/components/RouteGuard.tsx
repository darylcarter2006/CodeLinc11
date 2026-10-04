import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { areaFor, useApp } from '../state/context'

const HOME = { auth: '/auth', onboarding: '/onboarding', app: '/dashboard' } as const

/** While a signed-in person's saved answers load, or if they couldn't be loaded. */
function ProfilePending() {
  const { profileStatus, retryLoad } = useApp()
  if (profileStatus === 'error')
    return (
      <section className="card pad pending" role="alert">
        <h2>We couldn't load your saved answers</h2>
        <p>Check your connection, then try again.</p>
        <button className="btn" type="button" onClick={retryLoad}>
          Try again
        </button>
      </section>
    )
  return (
    <p className="muted pending" role="status">
      Loading your saved answers…
    </p>
  )
}

const loading = (state: ReturnType<typeof useApp>) =>
  !state.isExample && !!state.account && (state.profileStatus === 'loading' || state.profileStatus === 'error')

/** Render children only if the user belongs in `area`; otherwise redirect to where they belong. */
export function RouteGuard({ area, children }: { area: keyof typeof HOME; children: ReactNode }) {
  const state = useApp()
  if (loading(state)) return <ProfilePending />
  const current = areaFor(state)
  return current === area ? children : <Navigate to={HOME[current]} replace />
}

export function HomeRedirect() {
  const state = useApp()
  if (loading(state)) return <ProfilePending />
  return <Navigate to={HOME[areaFor(state)]} replace />
}
