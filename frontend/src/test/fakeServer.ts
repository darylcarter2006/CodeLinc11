import { vi } from 'vitest'

/*
 * An in-memory stand-in for the backend's account, profile and support endpoints, installed as
 * `fetch`. AI endpoints answer 404, so the app uses its local parser and standard answers.
 */

interface FakeUser {
  id: string
  email: string
  name: string
  password: string | null
}

export interface FakeServerOptions {
  /** Status for POST /v1/support/callback-requests (default 201). */
  supportStatus?: number
  /** Accept Google credentials of the form "good:<sub>:<email>" (default true). */
  google?: boolean
  /** Reply for POST /v1/ai/chat (default: 404, so Chat uses standard answers). */
  chat?: () => Response
}

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
const apiError = (status: number, code: string, message = code) => json({ error: { code, message, request_id: 'req_test' } }, status)

export function installFakeServer({ supportStatus = 201, google = true, chat }: FakeServerOptions = {}) {
  const users = new Map<string, FakeUser>()
  const tokens = new Map<string, string>()
  const states = new Map<string, unknown>()
  const resets = new Map<string, string>()
  const sentResets: { email: string; token: string }[] = []
  let seq = 0

  const signIn = (user: FakeUser, status = 200) => {
    const token = (++seq).toString(16).padStart(64, 'a')
    tokens.set(token, user.id)
    return json(
      {
        access_token: token,
        expires_at: new Date(Date.now() + 3600_000).toISOString(),
        user: { id: user.id, email: user.email, name: user.name, given_name: user.name, picture: null, has_password: user.password !== null },
      },
      status,
    )
  }
  const byEmail = (email: string) => [...users.values()].find((u) => u.email === email)
  const create = (email: string, name: string, password: string | null) => {
    const user = { id: `usr_${++seq}`, email, name, password }
    users.set(user.id, user)
    return user
  }

  const handle = async (url: string, init: RequestInit = {}): Promise<Response> => {
    const path = url.replace(/^.*\/v1/, '')
    const method = init.method ?? 'GET'
    const body = init.body ? JSON.parse(String(init.body)) : {}
    const auth = new Headers(init.headers).get('Authorization')?.replace('Bearer ', '') ?? ''
    const userId = tokens.get(auth)
    const signedIn = userId ? users.get(userId) : undefined

    if (path === '/ai/chat' && chat) return chat()
    if (path.startsWith('/ai/')) return new Response(null, { status: 404 })
    if (path === '/support/callback-requests') return supportStatus === 201 ? json({ id: 'cbk_1' }, 201) : new Response(null, { status: supportStatus })

    if (path === '/auth/signup') {
      const email = String(body.email).trim().toLowerCase()
      if (byEmail(email)) return apiError(409, 'email_taken', 'An account with this email already exists. Log in instead.')
      if (String(body.password).length < 8) return apiError(422, 'weak_password', 'Use at least 8 characters for your password.')
      return signIn(create(email, body.name, body.password), 201)
    }
    if (path === '/auth/login') {
      const user = byEmail(String(body.email).trim().toLowerCase())
      if (!user || user.password === null || user.password !== body.password)
        return apiError(401, 'invalid_login', "That email and password don't match. Try again, or reset your password.")
      return signIn(user)
    }
    if (path === '/auth/google') {
      if (!google) return apiError(503, 'auth_unavailable')
      const [kind, sub, email] = String(body.credential).split(':')
      if (kind !== 'good' || !sub || !email) return apiError(401, 'invalid_credential')
      return signIn(byEmail(email) ?? create(email, 'Ada', null))
    }
    if (path === '/auth/password-reset/request') {
      const user = byEmail(String(body.email).trim().toLowerCase())
      if (user) {
        const token = (++seq).toString(16).padStart(64, 'b')
        resets.set(token, user.id)
        sentResets.push({ email: user.email, token })
      }
      return new Response(null, { status: 202 })
    }
    if (path === '/auth/password-reset/confirm') {
      const id = resets.get(body.token)
      if (!id) return apiError(400, 'reset_link_invalid', 'This reset link has expired or was already used. Request a new one.')
      resets.delete(body.token)
      const user = users.get(id)!
      user.password = body.new_password
      for (const [t, u] of tokens) if (u === id) tokens.delete(t)
      return signIn(user)
    }

    if (!signedIn) return apiError(401, 'unauthorized')
    if (path === '/auth/logout') {
      tokens.delete(auth)
      return new Response(null, { status: 204 })
    }
    if (path === '/auth/password') {
      if (signedIn.password === null) return apiError(409, 'password_not_set', 'This account signs in with Google.')
      if (signedIn.password !== body.current_password) return apiError(401, 'invalid_login', "Your current password isn't right.")
      signedIn.password = body.new_password
      return new Response(null, { status: 204 })
    }
    if (path === '/account' && method === 'DELETE') {
      if (signedIn.password !== null && body.password !== signedIn.password) return apiError(401, 'invalid_login', "Your password isn't right.")
      users.delete(signedIn.id)
      states.delete(signedIn.id)
      for (const [t, u] of tokens) if (u === signedIn.id) tokens.delete(t)
      return new Response(null, { status: 204 })
    }
    if (path === '/account/profile' && method === 'GET') return json({ state: states.get(signedIn.id) ?? null, updated_at: null })
    if (path === '/account/profile' && method === 'PUT') {
      states.set(signedIn.id, structuredClone(body))
      return json({ state: body, updated_at: new Date().toISOString() })
    }
    return apiError(404, 'not_found')
  }

  const fetch = vi.fn(handle)
  vi.stubGlobal('fetch', fetch)
  return {
    fetch,
    users,
    tokens,
    /** The saved state for an email's account, as the server holds it. */
    stateOf: (email: string) => {
      const user = byEmail(email)
      return user ? states.get(user.id) : undefined
    },
    sentResets,
    /** Make the next profile requests fail with this status (0: network error), until cleared with null. */
    failProfile(status: number | null) {
      fetch.mockImplementation(async (url: string, init?: RequestInit) => {
        if (status !== null && url.includes('/account/profile')) {
          if (status === 0) throw new TypeError('offline')
          return apiError(status, status === 401 ? 'unauthorized' : 'server_error')
        }
        return handle(url, init)
      })
    },
  }
}

export type FakeServer = ReturnType<typeof installFakeServer>
