import { createContext, useContext } from 'react'
import type { PolicyType } from '../domain/policy'
import type { ChangeLogEntry, PolicyField, Profile, SavedProfile } from '../domain/profile'
import type { Account, ActionResult, AuthResult } from '../services/auth'
import type { StepsChecked } from '../services/profileStore'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  /** Small source note under an assistant answer, e.g. for canned answers. */
  note?: string
}

/** The signed-in person's saved state: not signed in, loading from the server, loaded, or failed to load. */
export type ProfileStatus = 'idle' | 'loading' | 'ready' | 'error'

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
  profileStatus: ProfileStatus
  /** Try loading the saved state again after an error. */
  retryLoad(): void
  /** The latest change hasn't reached the server yet (it keeps retrying). */
  saveFailed: boolean
  /** A message for the sign-in page, e.g. after a sign-in expires. */
  notice: string | null
  signUp(name: string, email: string, password: string): Promise<AuthResult>
  logIn(email: string, password: string): Promise<AuthResult>
  signInWithGoogle(credential: string): Promise<AuthResult>
  requestPasswordReset(email: string): Promise<ActionResult>
  /** Set a new password from a reset link, and sign in. */
  resetPassword(token: string, password: string): Promise<AuthResult>
  changePassword(current: string, next: string): Promise<ActionResult>
  leave(): void
  enterExample(): void
  updateSaved(next: SavedProfile): void
  confirmProfile(): void
  /** `policyChosen`: coverage-type questions the person picked an answer for in this save. */
  saveInfo(next: Profile, changes: string[], policyChosen?: PolicyField[]): void
  /** The coverage type the result pop-up last showed (null: never shown). */
  policySeen: PolicyType | null
  markPolicySeen(type: PolicyType): void
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
