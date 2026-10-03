import { createContext, useContext } from 'react'
import type { ChangeLogEntry, Profile, SavedProfile } from '../domain/profile'
import type { Account, AuthResult } from '../services/auth'
import type { StepsChecked } from '../services/profileStore'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  /** Small source note under an assistant answer, e.g. for canned answers. */
  note?: string
}

export interface AppState {
  account: Account | null
  isExample: boolean
  /** The profile on screen: the example copy in example mode, else the saved one. */
  profile: Profile
  saved: SavedProfile
  log: ChangeLogEntry[]
  steps: StepsChecked
  chat: ChatMessage[]
  chatBusy: boolean
  signUp(name: string, email: string, password: string): AuthResult
  logIn(email: string, password: string): AuthResult
  leave(): void
  enterExample(): void
  updateSaved(next: SavedProfile): void
  confirmProfile(): void
  saveInfo(next: Profile, changes: string[]): void
  toggleStep(text: string, checked: boolean): void
  askChat(question: string): Promise<void>
  resetChat(): void
}

export const AppContext = createContext<AppState | null>(null)

export function useApp(): AppState {
  const ctx = useContext(AppContext)
  if (!ctx) throw new Error('useApp must be used inside <AppProvider>')
  return ctx
}

/** Which area the current user belongs in (prototype `route()`). */
export function areaFor(state: Pick<AppState, 'account' | 'isExample' | 'saved'>): 'auth' | 'onboarding' | 'app' {
  if (state.isExample) return 'app'
  if (!state.account) return 'auth'
  return state.saved.confirmed ? 'app' : 'onboarding'
}
