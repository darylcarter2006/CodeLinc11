import { googleClientId, readGoogleCredential } from './google'
import { storage } from './storage'

/* Auth behind an interface so a real provider can replace the local one. Passwords are never stored. */

export interface Account {
  name: string
  email: string
}

/** `isNew` is true when this call created the account, so the caller starts a fresh profile. */
export type AuthResult = { ok: true; account: Account; isNew: boolean } | { ok: false; error: string }

export interface AuthService {
  /** The signed-in account, or null. */
  current(): Account | null
  signUp(name: string, email: string, password: string): AuthResult
  logIn(email: string, password: string): AuthResult
  /** Sign up or log in with a Google ID token (one button does both). */
  signInWithGoogle(credential: string): AuthResult
  signOut(): void
}

/**
 * Prototype provider: one account per browser. The password is checked by the form and then
 * discarded; the Google token is read for name and email and then discarded.
 */
export const localAuth: AuthService = {
  current() {
    const account = storage.get<Account>('account')
    return account && storage.get<boolean>('session') ? account : null
  },
  signUp(name, email) {
    const existing = storage.get<Account>('account')
    if (existing && existing.email === email)
      return { ok: false, error: 'An account with this email already exists in this browser. Log in instead.' }
    const account = { name, email }
    storage.set('account', account)
    storage.set('session', true)
    return { ok: true, account, isNew: true }
  },
  logIn(email) {
    const existing = storage.get<Account>('account')
    if (!existing || existing.email !== email)
      return { ok: false, error: "We couldn't find an account with that email in this browser. Sign up to create one." }
    storage.set('session', true)
    return { ok: true, account: existing, isNew: false }
  },
  signInWithGoogle(credential) {
    const clientId = googleClientId()
    const profile = clientId ? readGoogleCredential(credential, clientId) : null
    if (!profile) return { ok: false, error: "Google sign-in didn't work. Try again, or use your email instead." }
    const existing = storage.get<Account>('account')
    storage.set('session', true)
    if (existing && existing.email === profile.email) return { ok: true, account: existing, isNew: false }
    const account = { name: profile.name, email: profile.email }
    storage.set('account', account)
    return { ok: true, account, isNew: true }
  },
  signOut() {
    storage.set('session', null)
  },
}
