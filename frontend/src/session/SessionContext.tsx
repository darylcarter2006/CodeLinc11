import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, ApiError, newClientRequestId } from '../api/client'
import type {
  AssessmentResponse,
  MessageOut,
  ProfileFieldName,
  ProfileResponse,
  ProfileUpdates,
  SessionResponse,
} from '../api/types'
import { SessionContext, type SessionContextValue } from './context'

// Sessions are anonymous and short-lived (4h). sessionStorage clears when the tab closes,
// which fits that better than localStorage.
const STORAGE_KEY = 'needs-analyzer-session'

interface StoredSession {
  sessionId: string
  token: string
  expiresAt: string
}

function loadStored(): StoredSession | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as StoredSession) : null
  } catch {
    return null
  }
}

function saveStored(value: StoredSession | null) {
  try {
    if (value) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(value))
    else sessionStorage.removeItem(STORAGE_KEY)
  } catch {
    // Storage unavailable (private mode etc.); the session just won't survive a reload.
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [stored, setStored] = useState<StoredSession | null>(null)
  const [status, setStatus] = useState<SessionContextValue['status']>('loading')
  const [error, setError] = useState<string | null>(null)
  const [state, setState] = useState<ProfileResponse | null>(null)
  const [messages, setMessages] = useState<MessageOut[]>([])
  const [turns, setTurns] = useState<{ count: number; limit: number } | null>(null)
  const [savedAssessment, setSavedAssessment] = useState<AssessmentResponse | null>(null)
  const [busy, setBusy] = useState(false)

  const applySession = useCallback((session: SessionResponse) => {
    setState(session)
    setTurns({ count: session.turn_count, limit: session.turn_limit })
  }, [])

  const createNew = useCallback(async () => {
    const created = await api.createSession()
    const next = { sessionId: created.session_id, token: created.access_token, expiresAt: created.expires_at }
    saveStored(next)
    setStored(next)
    const session = await api.getSession(next.sessionId, next.token)
    applySession(session)
    setMessages([])
    setSavedAssessment(null)
  }, [applySession])

  // Restore an existing session on load, or start a new one if it expired or is gone.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const existing = loadStored()
        if (existing) {
          try {
            const [session, history] = await Promise.all([
              api.getSession(existing.sessionId, existing.token),
              api.getMessages(existing.sessionId, existing.token),
            ])
            if (cancelled) return
            setStored(existing)
            applySession(session)
            setMessages(history.messages)
            setStatus('ready')
            return
          } catch (e) {
            if (!(e instanceof ApiError) || ![401, 404].includes(e.status)) throw e
          }
        }
        if (!cancelled) await createNew()
        if (!cancelled) setStatus('ready')
      } catch (e) {
        if (cancelled) return
        setError(e instanceof Error ? e.message : String(e))
        setStatus('error')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [applySession, createNew])

  /** Re-read the server state, e.g. after a stale_revision conflict. */
  const reload = useCallback(async (s: StoredSession) => {
    const [session, history] = await Promise.all([
      api.getSession(s.sessionId, s.token),
      api.getMessages(s.sessionId, s.token),
    ])
    applySession(session)
    setMessages(history.messages)
  }, [applySession])

  const run = useCallback(
    async (action: (s: StoredSession, revision: number) => Promise<void>) => {
      if (!stored || !state) return
      setBusy(true)
      setError(null)
      try {
        await action(stored, state.revision)
      } catch (e) {
        if (e instanceof ApiError && e.code === 'stale_revision') {
          await reload(stored)
          setError('Your answers changed in another tab or request. We reloaded the latest version; please try again.')
        } else if (e instanceof ApiError && (e.code === 'session_expired' || e.code === 'not_found')) {
          setError('Your session expired, so we started a new one.')
          await createNew()
        } else {
          setError(e instanceof Error ? e.message : String(e))
        }
      } finally {
        setBusy(false)
      }
    },
    [stored, state, reload, createNew],
  )

  const sendMessage = useCallback(
    (text: string) =>
      run(async (s, revision) => {
        const optimistic: MessageOut = {
          id: `local-${Date.now()}`,
          role: 'user',
          content: text,
          created_at: new Date().toISOString(),
        }
        setMessages((m) => [...m, optimistic])
        try {
          const res = await api.postMessage(s.sessionId, s.token, {
            text,
            expected_revision: revision,
            client_request_id: newClientRequestId(),
          })
          setState(res)
          setTurns((t) => (t ? { ...t, count: t.count + 1 } : t))
          setMessages((m) => [
            ...m,
            { id: `local-a-${Date.now()}`, role: 'assistant', content: res.assistant_message, created_at: new Date().toISOString() },
          ])
        } catch (e) {
          setMessages((m) => m.filter((msg) => msg.id !== optimistic.id))
          throw e
        }
      }),
    [run],
  )

  const updateProfile = useCallback(
    (updates: ProfileUpdates, confirm: ProfileFieldName[] = []) =>
      run(async (s, revision) => {
        const res = await api.patchProfile(s.sessionId, s.token, {
          expected_revision: revision,
          client_request_id: newClientRequestId(),
          updates,
          confirm,
        })
        setState(res)
      }),
    [run],
  )

  const saveAssessment = useCallback(
    () =>
      run(async (s, revision) => {
        setSavedAssessment(await api.saveAssessment(s.sessionId, s.token, revision))
      }),
    [run],
  )

  const startOver = useCallback(async () => {
    setBusy(true)
    try {
      if (stored) await api.deleteSession(stored.sessionId, stored.token).catch(() => undefined)
      await createNew()
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }, [stored, createNew])

  const value = useMemo<SessionContextValue>(
    () => ({
      status,
      error,
      state,
      messages,
      turnsRemaining: turns ? Math.max(0, turns.limit - turns.count) : null,
      savedAssessment,
      busy,
      sendMessage,
      updateProfile,
      saveAssessment,
      startOver,
      clearError: () => setError(null),
    }),
    [status, error, state, messages, turns, savedAssessment, busy, sendMessage, updateProfile, saveAssessment, startOver],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}
