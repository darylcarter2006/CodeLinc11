import { useState, type FormEvent } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { GoogleButton } from '../components/GoogleButton'
import { useApp } from '../state/context'

type Mode = 'signup' | 'login' | 'forgot'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/* Sign up / log in / reset a forgotten password, with a shortcut into example mode. The guard redirects once signed in. */
export function AuthPage() {
  const { signUp, logIn, signInWithGoogle, requestPasswordReset, enterExample, notice } = useApp()
  const location = useLocation()
  const [mode, setMode] = useState<Mode>((location.state as { mode?: Mode } | null)?.mode ?? (notice ? 'login' : 'signup'))
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [googleError, setGoogleError] = useState('')
  const [busy, setBusy] = useState(false)
  const [resetSent, setResetSent] = useState(false)

  const switchMode = (m: Mode) => {
    setMode(m)
    setError('')
    setGoogleError('')
    setResetSent(false)
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (busy) return
    const n = name.trim()
    const em = email.trim().toLowerCase()
    if (mode === 'signup' && !n) return setError('Enter your first name.')
    if (!EMAIL_RE.test(em)) return setError('Enter a valid email address, like you@example.com.')
    if (mode === 'signup' && password.length < 8) return setError('Use at least 8 characters for your password.')
    if (mode === 'signup' && password.length > 128) return setError('Use at most 128 characters for your password.')
    if (mode === 'login' && !password) return setError('Enter your password.')
    setError('')
    setBusy(true)
    if (mode === 'forgot') {
      const result = await requestPasswordReset(em)
      setBusy(false)
      if (result.ok) setResetSent(true)
      else setError(result.error)
      return
    }
    const result = mode === 'signup' ? await signUp(n, em, password) : await logIn(em, password)
    setBusy(false)
    if (!result.ok) {
      setPassword('')
      setError(result.error)
    }
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
        {notice && (
          <p className="notice" role="status">
            {notice}
          </p>
        )}
        <div className="seg-ctl" role="group" aria-label="Sign up or log in">
          <button type="button" aria-pressed={mode === 'signup'} onClick={() => switchMode('signup')}>
            Sign up
          </button>
          <button type="button" aria-pressed={mode !== 'signup'} onClick={() => switchMode('login')}>
            Log in
          </button>
        </div>
        {mode === 'forgot' ? (
          <ForgotPassword
            email={email}
            setEmail={setEmail}
            error={error}
            busy={busy}
            sent={resetSent}
            onSubmit={submit}
            onBack={() => switchMode('login')}
          />
        ) : (
          <>
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
              {mode === 'login' && (
                <button className="linkish small forgot" type="button" onClick={() => switchMode('forgot')}>
                  Forgot password?
                </button>
              )}
              <div className="err" role="alert">
                {error}
              </div>
              <button className="btn full" type="submit" disabled={busy}>
                {busy ? 'One moment…' : mode === 'signup' ? 'Create account' : 'Log in'}
              </button>
              <p className="fine">
                Your answers are saved to your account so you can pick up on any device. Passwords are stored only as a secure
                hash.
                {mode === 'signup' && (
                  <>
                    {' '}
                    By creating an account, you agree to the <Link to="/terms">terms of service</Link> and{' '}
                    <Link to="/privacy">privacy policy</Link>.
                  </>
                )}
              </p>
            </form>
          </>
        )}
        <div className="auth-alt">
          <button className="linkish" type="button" onClick={enterExample}>
            Explore with example data instead
          </button>
        </div>
      </div>
    </section>
  )
}

interface ForgotProps {
  email: string
  setEmail(email: string): void
  error: string
  busy: boolean
  sent: boolean
  onSubmit(e: FormEvent): void
  onBack(): void
}

/* "Forgot password?": ask for a reset link. The reply is the same whether or not the email has an account. */
function ForgotPassword({ email, setEmail, error, busy, sent, onSubmit, onBack }: ForgotProps) {
  return (
    <div className="stack">
      <h3 className="side-title">Reset your password</h3>
      {sent ? (
        <p role="status">
          If there's an account for <strong>{email.trim().toLowerCase()}</strong>, we've sent it a link to choose a new password. The
          link works once and expires in 30 minutes. Check your spam folder if it doesn't arrive.
        </p>
      ) : (
        <form className="stack" onSubmit={onSubmit} noValidate>
          <p className="flush">Enter your account's email and we'll send you a link to choose a new password.</p>
          <div className="field">
            <label htmlFor="resetEmail">Email</label>
            <div className="in">
              <input id="resetEmail" type="email" autoComplete="email" placeholder="you@example.com" value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
          </div>
          <div className="err" role="alert">
            {error}
          </div>
          <button className="btn full" type="submit" disabled={busy}>
            {busy ? 'One moment…' : 'Email me a reset link'}
          </button>
        </form>
      )}
      <button className="linkish small" type="button" onClick={onBack}>
        Back to log in
      </button>
    </div>
  )
}
