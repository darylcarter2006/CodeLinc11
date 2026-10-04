import { HttpError, postJson, requestJson } from './http'
import { storage } from './storage'

/*
 * Accounts live on the server: email and password (hashed there with Argon2id) or Google. The
 * browser keeps only the account token, its expiry, and the name and email to show; never a
 * password. Behind an interface so tests can swap it.
 */

export interface Account {
  name: string
  email: string
  /** False for accounts that only sign in with Google (no password to change). */
  hasPassword: boolean
}

export type AuthResult = { ok: true; account: Account } | { ok: false; error: string }
export type ActionResult = { ok: true } | { ok: false; error: string }

export interface AuthService {
  /** The signed-in account, or null (also null once the token has expired). */
  current(): Account | null
  /** The account token for API calls, or null when signed out. */
  token(): string | null
  signUp(name: string, email: string, password: string): Promise<AuthResult>
  logIn(email: string, password: string): Promise<AuthResult>
  /** Sign up or log in with a Google ID token (one button does both). */
  signInWithGoogle(credential: string): Promise<AuthResult>
  /** Always answers the same way, whether or not the email has an account. */
  requestPasswordReset(email: string): Promise<ActionResult>
  /** Use a reset link's token; signs in on success. */
  resetPassword(token: string, password: string): Promise<AuthResult>
  changePassword(current: string, next: string): Promise<ActionResult>
  /** Forget the session in this browser (sign-out, or a token the server no longer accepts). */
  forget(): void
  /** Revoke a token on the server. Best effort: it expires there regardless. */
  revoke(token: string): Promise<void>
}

interface Session {
  token: string
  expiresAt: string
  account: Account
}

interface SignInResponse {
  access_token: string
  expires_at: string
  user: { email: string; name: string; given_name: string | null; has_password: boolean }
}

const SESSION_KEY = 'auth'
// Keys from the earlier browser-only sign-in. Removed on sign-out; on sign-in, profileStore's
// takeLegacyState() reads them first (to move an old profile into the account), then removes them.
const OLD_KEYS = ['account', 'session', 'token']

const readSession = (): Session | null => {
  const s = storage.get<Session>(SESSION_KEY)
  const valid = !!s && typeof s.token === 'string' && Date.parse(s.expiresAt) > Date.now() && typeof s.account?.email === 'string'
  return valid ? s : null
}

const UNREACHABLE = "We couldn't reach Coverage Compass. Check your connection and try again."
const GENERIC = 'Something went wrong. Please try again.'
// Server messages written for people; anything else gets a generic message.
const SHOWN = ['email_taken', 'invalid_login', 'weak_password', 'password_not_set', 'reset_link_invalid', 'reset_unavailable', 'session_expired']

/** A message for the person from a failed request. */
export function authErrorMessage(e: unknown): string {
  if (!(e instanceof HttpError)) return GENERIC
  if (e.status === 0 || e.status === 404 || e.code === 'http_error') return UNREACHABLE
  if (e.status === 429) return 'Too many attempts. Wait a few minutes and try again.'
  if (e.code === 'invalid_credential') return "Google sign-in didn't work. Try again, or use your email instead."
  if (e.code === 'auth_provider_unreachable') return "We couldn't reach Google to check your sign-in. Try again in a moment."
  if (e.code === 'auth_unavailable') return "Google sign-in isn't set up yet. Use your email for now."
  return SHOWN.includes(e.code) ? e.message : GENERIC
}

function startSession(res: SignInResponse | null): AuthResult {
  if (!res || typeof res.access_token !== 'string' || typeof res.user?.email !== 'string') return { ok: false, error: GENERIC }
  const account: Account = {
    name: res.user.given_name || res.user.name,
    email: res.user.email,
    hasPassword: res.user.has_password === true,
  }
  storage.set(SESSION_KEY, { token: res.access_token, expiresAt: res.expires_at, account } satisfies Session)
  return { ok: true, account }
}

async function signIn(path: string, body: unknown): Promise<AuthResult> {
  try {
    return startSession(await requestJson<SignInResponse>('POST', path, body))
  } catch (e) {
    return { ok: false, error: authErrorMessage(e) }
  }
}

export const serverAuth: AuthService = {
  current: () => readSession()?.account ?? null,
  token: () => readSession()?.token ?? null,
  signUp: (name, email, password) => signIn('/auth/signup', { name, email, password }),
  logIn: (email, password) => signIn('/auth/login', { email, password }),
  signInWithGoogle: (credential) => signIn('/auth/google', { credential }),
  resetPassword: (token, password) => signIn('/auth/password-reset/confirm', { token, new_password: password }),

  async requestPasswordReset(email) {
    try {
      await postJson('/auth/password-reset/request', { email })
      return { ok: true }
    } catch (e) {
      return { ok: false, error: authErrorMessage(e) }
    }
  },

  async changePassword(current, next) {
    const token = readSession()?.token
    if (!token) return { ok: false, error: 'Your sign-in has expired. Please log in again.' }
    try {
      await postJson('/auth/password', { current_password: current, new_password: next }, { token })
      return { ok: true }
    } catch (e) {
      return { ok: false, error: authErrorMessage(e) }
    }
  },

  forget() {
    storage.set(SESSION_KEY, null)
    OLD_KEYS.forEach((k) => storage.set(k, null))
  },

  async revoke(token) {
    await postJson('/auth/logout', {}, { token }).catch(() => undefined)
  },
}
