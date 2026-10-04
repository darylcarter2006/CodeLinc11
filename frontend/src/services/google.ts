/*
 * Google Identity Services (GIS): loads Google's sign-in script. The ID token it returns goes to
 * the backend (/v1/auth/google, see services/auth.ts), which verifies its signature; the browser
 * never trusts the token's contents itself.
 */

const SCRIPT_SRC = 'https://accounts.google.com/gsi/client'

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
