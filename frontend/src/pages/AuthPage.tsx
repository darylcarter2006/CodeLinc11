import { useState, type FormEvent } from 'react'
import { useLocation } from 'react-router-dom'
import { GoogleButton } from '../components/GoogleButton'
import { useApp } from '../state/context'

type Mode = 'signup' | 'login'

/* Sign up / log in, with a shortcut into example mode. The guard redirects once this succeeds. */
export function AuthPage() {
  const { signUp, logIn, signInWithGoogle, enterExample } = useApp()
  const location = useLocation()
  const [mode, setMode] = useState<Mode>((location.state as { mode?: Mode } | null)?.mode ?? 'signup')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [googleError, setGoogleError] = useState('')

  const switchMode = (m: Mode) => {
    setMode(m)
    setError('')
    setGoogleError('')
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const n = name.trim()
    const em = email.trim().toLowerCase()
    if (mode === 'signup' && !n) return setError('Enter your first name.')
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(em)) return setError('Enter a valid email address, like you@example.com.')
    if (mode === 'signup' && password.length < 8) return setError('Use at least 8 characters for your password.')
    if (mode === 'login' && !password) return setError('Enter your password.')
    const result = mode === 'signup' ? signUp(n, em, password) : logIn(em, password)
    setPassword('')
    if (!result.ok) setError(result.error)
  }

  return (
    <section className="auth">
      <div className="pitch">
        <div className="eyebrow">Life insurance, right-sized</div>
        <h2>Find the coverage that fits your life, in a short conversation.</h2>
        <p>
          No forms to wrestle with. Tell us about your situation in your own words, and we'll show you a clear starting
          point with every number explained.
        </p>
        <ol>
          <li>Create an account</li>
          <li>Chat for about three minutes</li>
          <li>See your dashboard, and update it as life changes</li>
        </ol>
      </div>
      <div className="card auth-card">
        <div className="seg-ctl" role="group" aria-label="Sign up or log in">
          <button type="button" aria-pressed={mode === 'signup'} onClick={() => switchMode('signup')}>
            Sign up
          </button>
          <button type="button" aria-pressed={mode === 'login'} onClick={() => switchMode('login')}>
            Log in
          </button>
        </div>
        <GoogleButton
          mode={mode}
          onCredential={(credential) => {
            setGoogleError('')
            void signInWithGoogle(credential).then((result) => {
              if (!result.ok) setGoogleError(result.error)
            })
          }}
          onError={setGoogleError}
        />
        {googleError && (
          <div className="err google-err" role="alert">
            {googleError}
          </div>
        )}
        <div className="or-rule">
          <span>or {mode === 'signup' ? 'sign up' : 'log in'} with email</span>
        </div>
        <form className="stack" onSubmit={submit} noValidate>
          {mode === 'signup' && (
            <div className="field">
              <label htmlFor="authName">First name</label>
              <div className="in">
                <input id="authName" autoComplete="given-name" placeholder="Jordan" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
            </div>
          )}
          <div className="field">
            <label htmlFor="authEmail">Email</label>
            <div className="in">
              <input id="authEmail" type="email" autoComplete="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
          </div>
          <div className="field">
            <label htmlFor="authPass">Password</label>
            <div className="in">
              <input
                id="authPass"
                type="password"
                autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                placeholder="At least 8 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
          </div>
          <div className="err" role="alert">
            {error}
          </div>
          <button className="btn full" type="submit">
            {mode === 'signup' ? 'Create account' : 'Log in'}
          </button>
          <p className="fine">Prototype sign-in: your details stay in this browser and passwords are never stored or sent anywhere.</p>
        </form>
        <div className="auth-alt">
          <button className="linkish" type="button" onClick={enterExample}>
            Explore with example data instead
          </button>
        </div>
      </div>
    </section>
  )
}
