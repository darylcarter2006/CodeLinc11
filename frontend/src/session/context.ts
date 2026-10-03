import { createContext, useContext } from 'react'
import type { AssessmentResponse, MessageOut, ProfileFieldName, ProfileResponse, ProfileUpdates } from '../api/types'

export interface SessionContextValue {
  status: 'loading' | 'ready' | 'error'
  error: string | null
  state: ProfileResponse | null
  messages: MessageOut[]
  turnsRemaining: number | null
  savedAssessment: AssessmentResponse | null
  busy: boolean
  sendMessage: (text: string) => Promise<void>
  updateProfile: (updates: ProfileUpdates, confirm?: ProfileFieldName[]) => Promise<void>
  saveAssessment: () => Promise<void>
  startOver: () => Promise<void>
  clearError: () => void
}

export const SessionContext = createContext<SessionContextValue | null>(null)

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error('useSession must be used inside <SessionProvider>')
  return ctx
}
