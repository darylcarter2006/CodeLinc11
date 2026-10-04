import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useApp } from '../state/context'

/** The token from a reset link (/reset-password#token=...). */
function tokenFromHash(hash: string): string | null {
  const token = new URLSearchParams(hash.slice(1)).get('token')
  return token && /^[0-9a-f]{64}$/.test(token) ? token : null
}

/* Choose a new password from an emailed reset link; signs in on success. */
export function ResetPasswordPage() {
  const { resetPassword } = useApp()
  const navigate = useNavigate()
  const location = useLocation()
  // Read once, then dropped from the address bar and history so the link can't be reused from there.
  const [token] = useState(() => tokenFromHash(location.hash))
  useEffect(() => {
    if (location.hash) navigate(location.pathname, { replace: true })
  }, [location.hash, location.pathname, navigate])
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (busy || !token) return
    if (password.length < 8) return setError('Use at least 8 characters for your password.')
    if (password.length > 128) return setError('Use at most 128 characters for your password.')
    if (password !== confirm) return setError("The two passwords don't match.")
    setError('')
    setBusy(true)
    const result = await resetPassword(token, password)
    setBusy(false)
    if (result.ok) navigate('/', { replace: true })
    else setError(result.error)
  }

  return (
    <section className="card pad narrow">
      <div className="eyebrow">Password reset</div>
      <h2>Choose a new password</h2>
      {token ? (
        <form className="stack" onSubmit={submit} noValidate>
          <p className="flush">After this, you'll be signed in here and signed out on every other device.</p>
          <div className="field">
            <label htmlFor="newPass">New password</label>
            <div className="in">
              <input id="newPass" type="password" autoComplete="new-password" placeholder="At least 8 characters" value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
          </div>
          <div className="field">
            <label htmlFor="newPass2">Type it again</label>
            <div className="in">
              <input id="newPass2" type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            </div>
          </div>
          <div className="err" role="alert">
            {error}
          </div>
          <button className="btn full" type="submit" disabled={busy}>
            {busy ? 'One moment…' : 'Save new password'}
          </button>
        </form>
      ) : (
        <p role="alert">
          This reset link is incomplete. Open the link from the email again, or{' '}
          <Link to="/auth" state={{ mode: 'forgot' }}>
            request a new one
          </Link>
          .
        </p>
      )}
    </section>
  )
}
