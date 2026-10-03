import { useEffect, useRef, useState } from 'react'
import { googleClientId, loadGoogleIdentity } from '../services/google'

interface Props {
  mode: 'signup' | 'login'
  onCredential: (credential: string) => void
  onError: (message: string) => void
}

// GIS should be initialized once per page; its callback forwards to whichever button is mounted.
let initializedFor: string | null = null
let forward: ((credential: string) => void) | null = null

/**
 * "Sign up / Sign in with Google". Renders Google's own button when VITE_GOOGLE_CLIENT_ID is set;
 * otherwise a look-alike that explains Google sign-in isn't set up yet.
 */
export function GoogleButton({ mode, onCredential, onError }: Props) {
  const clientId = googleClientId()
  const slot = useRef<HTMLDivElement>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    forward = onCredential
  }, [onCredential])

  useEffect(() => {
    if (!clientId) return
    let cancelled = false
    loadGoogleIdentity().then(
      (gis) => {
        if (cancelled || !slot.current) return
        if (initializedFor !== clientId) {
          gis.initialize({ client_id: clientId, callback: (r) => forward?.(r.credential) })
          initializedFor = clientId
        }
        slot.current.replaceChildren()
        gis.renderButton(slot.current, {
          type: 'standard',
          theme: 'outline',
          size: 'large',
          shape: 'pill',
          text: mode === 'signup' ? 'signup_with' : 'signin_with',
          logo_alignment: 'center',
          width: Math.min(400, Math.max(200, slot.current.offsetWidth || 384)),
        })
      },
      () => !cancelled && setFailed(true),
    )
    return () => {
      cancelled = true
    }
  }, [clientId, mode])

  if (clientId && !failed) return <div className="google-slot" ref={slot} data-testid="google-slot" />

  return (
    <button
      type="button"
      className="google-btn"
      onClick={() =>
        onError(
          failed
            ? "Google sign-in couldn't load. Check your connection, or use your email instead."
            : "Google sign-in isn't set up yet. Use your email for now.",
        )
      }
    >
      <GoogleLogo />
      {mode === 'signup' ? 'Sign up with Google' : 'Sign in with Google'}
    </button>
  )
}

function GoogleLogo() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden>
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  )
}
