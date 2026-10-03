import { exchangeCredential, revokeToken } from './googleAuth'
import { storage } from './storage'

/* Auth behind an interface so a real provider can replace the local one. Passwords are never stored. */

export interface Account {
  name: string
  email: string
  /** "google" when signed in through the backend; absent for the browser-only prototype account. */
  provider?: 'google'
}

export type AuthResult = { ok: true; account: Account } | { ok: false; error: string }

export interface AuthService {
  /** The signed-in account, or null. */
  current(): Account | null
  signUp(name: string, email: string, password: string): AuthResult
  logIn(email: string, password: string): AuthResult
  /** Exchange a Google Identity Services credential for a backend account token. */
  signInWithGoogle(credential: string): Promise<AuthResult>
  signOut(): void
}

interface StoredToken {
  token: string
  expiresAt: string
}

const tokenValid = (t: StoredToken | null): t is StoredToken => !!t && Date.parse(t.expiresAt) > Date.now()

/** Prototype provider: one account per browser. The password is checked by the form and then discarded. */
export const localAuth: AuthService = {
  current() {
    const account = storage.get<Account>('account')
    if (!account || !storage.get<boolean>('session')) return null
    // A Google account is only signed in while its backend token is still valid.
    if (account.provider === 'google' && !tokenValid(storage.get<StoredToken>('token'))) return null
    return account
  },
  signUp(name, email) {
    const existing = storage.get<Account>('account')
    if (existing && existing.email === email)
      return { ok: false, error: 'An account with this email already exists in this browser. Log in instead.' }
    const account = { name, email }
    storage.set('account', account)
    storage.set('session', true)
    storage.set('token', null)
    return { ok: true, account }
  },
  logIn(email) {
    const existing = storage.get<Account>('account')
    if (!existing || existing.email !== email || existing.provider === 'google')
      return { ok: false, error: "We couldn't find an account with that email in this browser. Sign up to create one." }
    storage.set('session', true)
    return { ok: true, account: existing }
  },
  async signInWithGoogle(credential) {
    try {
      const result = await exchangeCredential(credential)
      const account: Account = {
        name: result.user.given_name || result.user.name,
        email: result.user.email,
        provider: 'google',
      }
      storage.set('account', account)
      storage.set('session', true)
      storage.set('token', { token: result.access_token, expiresAt: result.expires_at } satisfies StoredToken)
      return { ok: true, account }
    } catch (e) {
      return { ok: false, error: e instanceof Error ? e.message : 'Google sign-in failed. Please try again.' }
    }
  },
  signOut() {
    const stored = storage.get<StoredToken>('token')
    storage.set('session', null)
    storage.set('token', null)
    if (stored) void revokeToken(stored.token)
  },
}
