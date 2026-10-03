import { storage } from './storage'

/* Auth behind an interface so a real provider can replace the local one. Passwords are never stored. */

export interface Account {
  name: string
  email: string
}

export type AuthResult = { ok: true; account: Account } | { ok: false; error: string }

export interface AuthService {
  /** The signed-in account, or null. */
  current(): Account | null
  signUp(name: string, email: string, password: string): AuthResult
  logIn(email: string, password: string): AuthResult
  signOut(): void
}

/** Prototype provider: one account per browser. The password is checked by the form and then discarded. */
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
    return { ok: true, account }
  },
  logIn(email) {
    const existing = storage.get<Account>('account')
    if (!existing || existing.email !== email)
      return { ok: false, error: "We couldn't find an account with that email in this browser. Sign up to create one." }
    storage.set('session', true)
    return { ok: true, account: existing }
  },
  signOut() {
    storage.set('session', null)
  },
}
