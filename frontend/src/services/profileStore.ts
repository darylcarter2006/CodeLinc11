import { blankProfile, blankSaved, type ChangeLogEntry, type SavedProfile } from '../domain/profile'
import type { PolicyType } from '../domain/policy'
import { storage } from './storage'

/* Profile persistence behind an interface so it can move to the backend later. */

export type StepsChecked = Record<string, boolean>

export interface ProfileStore {
  loadProfile(): SavedProfile
  saveProfile(saved: SavedProfile): void
  loadLog(): ChangeLogEntry[]
  saveLog(log: ChangeLogEntry[]): void
  loadSteps(): StepsChecked
  saveSteps(steps: StepsChecked): void
  /** The coverage type last shown in the result pop-up, so it only opens again when it changes. */
  loadPolicySeen(): PolicyType | null
  savePolicySeen(type: PolicyType | null): void
  /** Start a fresh profile, e.g. after sign-up. */
  reset(): void
}

export const localProfileStore: ProfileStore = {
  loadProfile: () => {
    const stored = storage.get<SavedProfile>('profile')
    if (!stored) return blankSaved()
    // Profiles saved before newer fields existed get their defaults; `known` still says they're unanswered.
    return { ...blankSaved(), ...stored, p: { ...blankProfile(), ...stored.p } }
  },
  saveProfile: (saved) => storage.set('profile', saved),
  loadLog: () => storage.get<ChangeLogEntry[]>('log') ?? [],
  saveLog: (log) => storage.set('log', log),
  loadSteps: () => storage.get<StepsChecked>('steps') ?? {},
  saveSteps: (steps) => storage.set('steps', steps),
  loadPolicySeen: () => storage.get<PolicyType>('policy-seen'),
  savePolicySeen: (type) => storage.set('policy-seen', type),
  reset() {
    storage.set('profile', blankSaved())
    storage.set('log', [])
    storage.set('steps', null)
    storage.set('policy-seen', null)
  },
}
