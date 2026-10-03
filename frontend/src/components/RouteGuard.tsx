import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { areaFor, useApp } from '../state/context'

const HOME = { auth: '/auth', onboarding: '/onboarding', app: '/dashboard' } as const

/** Render children only if the user belongs in `area`; otherwise redirect to where they belong. */
export function RouteGuard({ area, children }: { area: keyof typeof HOME; children: ReactNode }) {
  const current = areaFor(useApp())
  return current === area ? children : <Navigate to={HOME[current]} replace />
}

export function HomeRedirect() {
  return <Navigate to={HOME[areaFor(useApp())]} replace />
}
