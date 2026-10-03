/*
 * Google Identity Services (GIS): loads Google's sign-in script and handles the ID token it returns.
 * With the backend running, the token is sent to /v1/auth/google, which verifies its signature and
 * returns our own account token. Without a backend, the browser reads the token's claims for a
 * browser-only prototype account (like the email form); that path is never trusted by the server.
 */

import { HttpError, postJson } from './http'

const SCRIPT_SRC = 'https://accounts.google.com/gsi/client'
const ISSUERS = ['accounts.google.com', 'https://accounts.google.com']

export interface GoogleProfile {
  email: string
  name: string
}

interface GoogleIdApi {
  initialize(config: { client_id: string; callback: (response: { credential: string }) => void }): void
  renderButton(parent: HTMLElement, options: Record<string, unknown>): void
}

declare global {
  interface Window {
    google?: { accounts?: { id?: GoogleIdApi } }
  }
}

/** The OAuth client ID from VITE_GOOGLE_CLIENT_ID, or null when Google sign-in isn't set up. */
export const googleClientId = (): string | null => import.meta.env.VITE_GOOGLE_CLIENT_ID?.trim() || null

let loading: Promise<GoogleIdApi> | null = null

/** Load the GIS script once and resolve with its `google.accounts.id` API. */
export function loadGoogleIdentity(): Promise<GoogleIdApi> {
  const ready = window.google?.accounts?.id
  if (ready) return Promise.resolve(ready)
  loading ??= new Promise<GoogleIdApi>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = SCRIPT_SRC
    script.async = true
    script.onload = () => (window.google?.accounts?.id ? resolve(window.google.accounts.id) : reject(new Error('gis_missing')))
    script.onerror = () => {
      loading = null
      reject(new Error('gis_load_failed'))
    }
    document.head.append(script)
  })
  return loading
}

/** Decode a base64url JWT segment. */
function decodeSegment(segment: string): unknown {
  const b64 = segment.replace(/-/g, '+').replace(/_/g, '/').padEnd(Math.ceil(segment.length / 4) * 4, '=')
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))
  return JSON.parse(new TextDecoder().decode(bytes))
}

/**
 * Read name and email from a Google ID token, checking issuer, audience, expiry and that the
 * email is verified. Returns null for anything that doesn't pass.
 */
export function readGoogleCredential(credential: string, clientId: string, now = Date.now()): GoogleProfile | null {
  try {
    const parts = credential.split('.')
    if (parts.length !== 3) return null
    const claims = decodeSegment(parts[1]) as Record<string, unknown>
    if (!ISSUERS.includes(String(claims.iss))) return null
    if (claims.aud !== clientId) return null
    if (typeof claims.exp !== 'number' || claims.exp * 1000 <= now) return null
    if (claims.email_verified !== true || typeof claims.email !== 'string') return null
    const email = claims.email.trim().toLowerCase()
    const name = String(claims.given_name || claims.name || email.split('@')[0]).trim()
    return { email, name }
  } catch {
    return null
  }
}

/* Backend sign-in: the server verifies the token's signature and issues an account token. */

export interface SignedInUser {
  id: string
  email: string
  name: string
  given_name: string | null
  picture: string | null
}

export interface SignInResult {
  access_token: string
  expires_at: string
  user: SignedInUser
}

export type Exchange =
  | { kind: 'ok'; result: SignInResult }
  /** No backend sign-in here (not deployed, not configured, or unreachable): use the browser-only path. */
  | { kind: 'unavailable' }
  /** The backend looked at the token and said no, or can't sign in right now. Never fall back. */
  | { kind: 'error'; message: string }

// 404/501: endpoint not deployed. 0: backend unreachable. 503 auth_unavailable: no client ID set.
const UNAVAILABLE = [0, 404, 501]

/** Exchange Google's credential for our account token. */
export async function exchangeCredential(credential: string): Promise<Exchange> {
  try {
    const res = await postJson('/auth/google', { credential })
    return { kind: 'ok', result: (await res.json()) as SignInResult }
  } catch (e) {
    if (e instanceof HttpError) {
      if (UNAVAILABLE.includes(e.status) || e.code === 'auth_unavailable') return { kind: 'unavailable' }
      if (e.status === 503) return { kind: 'error', message: "We couldn't reach Google to check your sign-in. Try again in a moment." }
      if (e.status === 429) return { kind: 'error', message: 'Too many sign-in attempts. Wait a minute and try again.' }
    }
    return { kind: 'error', message: "Google sign-in didn't work. Try again, or use your email instead." }
  }
}

/** Revoke the account token on the server. Best effort: sign-out continues locally regardless. */
export async function revokeToken(token: string): Promise<void> {
  try {
    await postJson('/auth/logout', {}, { token })
  } catch {
    // Already expired or offline: nothing else to do.
  }
}
