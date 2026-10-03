import { blankSaved, type ChangeLogEntry, type SavedProfile } from '../domain/profile'
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
  /** Start a fresh profile, e.g. after sign-up. */
  reset(): void
}

export const localProfileStore: ProfileStore = {
  loadProfile: () => storage.get<SavedProfile>('profile') ?? blankSaved(),
  saveProfile: (saved) => storage.set('profile', saved),
  loadLog: () => storage.get<ChangeLogEntry[]>('log') ?? [],
  saveLog: (log) => storage.set('log', log),
  loadSteps: () => storage.get<StepsChecked>('steps') ?? {},
  saveSteps: (steps) => storage.set('steps', steps),
  reset() {
    storage.set('profile', blankSaved())
    storage.set('log', [])
    storage.set('steps', null)
  },
}
