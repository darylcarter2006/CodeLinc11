/*
 * Google Identity Services (GIS): loads Google's sign-in script and reads the ID token it returns.
 * The browser only checks the token's claims. Once real accounts exist, the backend must verify
 * the token's signature before trusting it.
 */

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
