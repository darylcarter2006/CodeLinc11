import { exchangeCredential, googleClientId, readGoogleCredential, revokeToken } from './google'
import { storage } from './storage'

/* Auth behind an interface so a real provider can replace the local one. Passwords are never stored. */

export interface Account {
  name: string
  email: string
  /** "google" when signed in through the backend; absent for browser-only accounts. */
  provider?: 'google'
}

/** `isNew` is true when this call created the account, so the caller starts a fresh profile. */
export type AuthResult = { ok: true; account: Account; isNew: boolean } | { ok: false; error: string }

export interface AuthService {
  /** The signed-in account, or null. */
  current(): Account | null
  signUp(name: string, email: string, password: string): AuthResult
  logIn(email: string, password: string): AuthResult
  /** Sign up or log in with a Google ID token (one button does both). */
  signInWithGoogle(credential: string): Promise<AuthResult>
  signOut(): void
}

interface StoredToken {
  token: string
  expiresAt: string
}

const tokenValid = (t: StoredToken | null): t is StoredToken => !!t && Date.parse(t.expiresAt) > Date.now()

const GOOGLE_FAILED = "Google sign-in didn't work. Try again, or use your email instead."

/**
 * One account per browser. The password is checked by the form and then discarded. A Google token
 * goes to the backend for verification; without a backend it is read for name and email only.
 */
export const localAuth: AuthService = {
  current() {
    const account = storage.get<Account>('account')
    if (!account || !storage.get<boolean>('session')) return null
    // A backend-verified Google account is only signed in while its account token is valid.
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
    return { ok: true, account, isNew: true }
  },
  logIn(email) {
    const existing = storage.get<Account>('account')
    if (!existing || existing.email !== email || existing.provider === 'google')
      return { ok: false, error: "We couldn't find an account with that email in this browser. Sign up to create one." }
    storage.set('session', true)
    return { ok: true, account: existing, isNew: false }
  },
  async signInWithGoogle(credential) {
    const existing = storage.get<Account>('account')
    const server = await exchangeCredential(credential)
    if (server.kind === 'error') return { ok: false, error: server.message }

    let account: Account
    if (server.kind === 'ok') {
      const { user, access_token, expires_at } = server.result
      account = { name: user.given_name || user.name, email: user.email, provider: 'google' }
      storage.set('token', { token: access_token, expiresAt: expires_at } satisfies StoredToken)
    } else {
      // No backend sign-in available: a browser-only account, exactly like the email form.
      const clientId = googleClientId()
      const profile = clientId ? readGoogleCredential(credential, clientId) : null
      if (!profile) return { ok: false, error: GOOGLE_FAILED }
      account = existing && existing.email === profile.email && !existing.provider ? existing : profile
      storage.set('token', null)
    }

    const isNew = !(existing && existing.email === account.email)
    storage.set('account', account)
    storage.set('session', true)
    return { ok: true, account, isNew }
  },
  signOut() {
    const stored = storage.get<StoredToken>('token')
    storage.set('session', null)
    storage.set('token', null)
    if (stored) void revokeToken(stored.token)
  },
}
