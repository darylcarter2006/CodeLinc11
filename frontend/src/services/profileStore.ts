import { blankProfile, blankSaved, type ChangeLogEntry, type SavedProfile } from '../domain/profile'
import type { PolicyType } from '../domain/policy'
import { requestJson } from './http'
import { storage } from './storage'

/*
 * A signed-in person's saved state lives on the server under their account (/v1/account/profile),
 * so it follows them to any device and nothing financial is left in a shared browser. Behind an
 * interface so tests can swap it.
 */

export type StepsChecked = Record<string, boolean>

export interface StoredState {
  saved: SavedProfile
  log: ChangeLogEntry[]
  steps: StepsChecked
  /** The coverage type last shown in the result pop-up, so it only opens again when it changes. */
  policySeen: PolicyType | null
}

export interface ProfileStore {
  /** The saved state, or null if this account hasn't saved anything yet. Throws HttpError. */
  load(token: string): Promise<StoredState | null>
  /** Replace the saved state. Throws HttpError. */
  save(token: string, state: StoredState): Promise<void>
}

// The server's limits (app/contracts/profile_state.py).
export const MAX_LOG = 50
const MAX_STEPS = 20

export const blankState = (): StoredState => ({ saved: blankSaved(), log: [], steps: {}, policySeen: null })

/** Fill in fields added since the state was saved; `known` still says which are unanswered. */
function normalize(stored: Partial<StoredState>): StoredState {
  const saved = stored.saved
  return {
    saved: saved ? { ...blankSaved(), ...saved, p: { ...blankProfile(), ...saved.p } } : blankSaved(),
    log: stored.log ?? [],
    steps: stored.steps ?? {},
    policySeen: stored.policySeen ?? null,
  }
}

/** Keep within the server's limits: the newest log entries, and only checklist items that are ticked. */
export function trimForSave(state: StoredState): StoredState {
  const ticked = Object.entries(state.steps).filter(([, on]) => on)
  return { ...state, log: state.log.slice(0, MAX_LOG), steps: Object.fromEntries(ticked.slice(-MAX_STEPS)) }
}

export const serverProfileStore: ProfileStore = {
  async load(token) {
    const res = await requestJson<{ state: Partial<StoredState> | null }>('GET', '/account/profile', undefined, { token })
    return res?.state ? normalize(res.state) : null
  },
  async save(token, state) {
    await requestJson('PUT', '/account/profile', trimForSave(state), { token })
  },
}

// Where the earlier browser-only version kept everything.
const LEGACY_KEYS = ['profile', 'log', 'steps', 'policy-seen', 'account', 'session', 'token']

/**
 * The profile the earlier browser-only version saved, if it belonged to this email. Every old key
 * is removed either way, so financial details don't stay behind in the browser.
 */
export function takeLegacyState(email: string): StoredState | null {
  const owner = storage.get<{ email?: string }>('account')
  const profile = storage.get<SavedProfile>('profile')
  const state =
    profile && owner?.email?.toLowerCase() === email.toLowerCase()
      ? normalize({
          saved: profile,
          log: storage.get<ChangeLogEntry[]>('log') ?? [],
          steps: storage.get<StepsChecked>('steps') ?? {},
          policySeen: storage.get<PolicyType>('policy-seen'),
        })
      : null
  LEGACY_KEYS.forEach((k) => storage.set(k, null))
  return state
}
