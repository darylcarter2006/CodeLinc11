import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import type { PolicyType } from '../domain/policy'
import { EXAMPLE, FLOW, POLICY_FIELDS, isPolicyField, type Profile, type SavedProfile } from '../domain/profile'
import { ChatError, ai, type ChatContext, type ChatTurn } from '../services/ai'
import { serverAuth, type Account, type AuthResult, type AuthService } from '../services/auth'
import { fallbackAnswer } from '../services/fallback'
import { HttpError } from '../services/http'
import {
  MAX_LOG,
  blankState,
  serverProfileStore,
  takeLegacyState,
  type ProfileStore,
  type StepsChecked,
  type StoredState,
} from '../services/profileStore'
import { AppContext, type AppState, type ChatMessage, type ProfileStatus } from './context'

/*
 * App-wide state: who is signed in, example mode, the saved profile, change log, next-step checks
 * and the Chat tab conversation. A signed-in person's state is loaded from their account and saved
 * back after every change; it is kept in memory only. Example mode never saves.
 */

interface Props {
  children: ReactNode
  auth?: AuthService
  store?: ProfileStore
}

let nextId = 0
const msgId = () => `m${++nextId}`
const SAVE_RETRY_MS = 10_000
const EXPIRED = 'Your sign-in has expired. Please log in again.'
const isUnauthorized = (e: unknown) => e instanceof HttpError && e.status === 401

export function AppProvider({ children, auth = serverAuth, store = serverProfileStore }: Props) {
  const [account, setAccount] = useState<Account | null>(() => auth.current())
  const [data, setData] = useState<StoredState>(blankState)
  const [profileStatus, setProfileStatus] = useState<ProfileStatus>(() => (auth.current() ? 'loading' : 'idle'))
  const [saveFailed, setSaveFailed] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [demo, setDemo] = useState<Profile | null>(null)
  const [demoSteps, setDemoSteps] = useState<StepsChecked>({})
  const [chat, setChat] = useState<ChatMessage[]>([])
  const [chatBusy, setChatBusy] = useState(false)

  const { saved, log, policySeen } = data
  const steps = demo === null ? data.steps : demoSteps
  const profile = demo ?? saved.p
  const turns = useRef<ChatTurn[]>([])
  const epoch = useRef(0)
  // Latest values for async chat requests. Layout effect so it's current before any child effect asks.
  const latest = useRef({ profile, account, demo: demo !== null, known: saved.known })
  useLayoutEffect(() => {
    latest.current = { profile, account, demo: demo !== null, known: saved.known }
  }, [profile, account, demo, saved.known])

  // Saving: one request at a time, and only the newest state is sent. `session` changes on every
  // sign-in and sign-out so a reply meant for an earlier session is ignored.
  const dataRef = useRef(data)
  const session = useRef(0)
  const queued = useRef<StoredState | null>(null)
  const inflight = useRef<Promise<void> | null>(null)
  const retry = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const retryFlush = useRef<() => void>(() => undefined)

  const replaceData = useCallback((next: StoredState) => {
    dataRef.current = next
    setData(next)
  }, [])

  const resetChat = useCallback(() => {
    epoch.current++
    turns.current = []
    setChat([])
    setChatBusy(false)
  }, [])

  /** Drop everything from the signed-in session, here only (the caller handles the server). */
  const clearSession = useCallback(() => {
    session.current++
    queued.current = null
    clearTimeout(retry.current)
    setAccount(null)
    replaceData(blankState())
    setProfileStatus('idle')
    setSaveFailed(false)
  }, [replaceData])

  const expire = useCallback(() => {
    auth.forget()
    clearSession()
    setNotice(EXPIRED)
  }, [auth, clearSession])

  const flush = useCallback((): Promise<void> => {
    if (inflight.current) return inflight.current
    const mine = session.current
    const run = async () => {
      while (queued.current && mine === session.current) {
        const next = queued.current
        queued.current = null
        const token = auth.token()
        if (!token) return expire()
        try {
          await store.save(token, next)
          if (mine === session.current) setSaveFailed(false)
        } catch (e) {
          if (mine !== session.current) return
          if (isUnauthorized(e)) return expire()
          queued.current ??= next
          setSaveFailed(true)
          retry.current = setTimeout(() => retryFlush.current(), SAVE_RETRY_MS)
          return
        }
      }
    }
    inflight.current = run().finally(() => {
      inflight.current = null
    })
    return inflight.current
  }, [auth, store, expire])
  useEffect(() => {
    retryFlush.current = () => void flush()
  }, [flush])

  /** Change the saved state and send it to the server. */
  const update = useCallback(
    (change: (s: StoredState) => StoredState) => {
      const next = change(dataRef.current)
      replaceData(next)
      if (account) {
        queued.current = next
        clearTimeout(retry.current)
        void flush()
      }
    },
    [account, replaceData, flush],
  )

  /** The account's saved state arrived; the first time, bring over a profile this browser kept before accounts. */
  const onLoaded = useCallback(
    (acct: Account, mine: number, stored: StoredState | null) => {
      if (mine !== session.current) return
      const legacy = takeLegacyState(acct.email)
      replaceData(stored ?? legacy ?? blankState())
      setProfileStatus('ready')
      if (!stored && legacy) {
        queued.current = legacy
        void flush()
      }
    },
    [replaceData, flush],
  )

  const onLoadFailed = useCallback(
    (mine: number, e: unknown) => {
      if (mine !== session.current) return
      if (isUnauthorized(e)) expire()
      else setProfileStatus('error')
    },
    [expire],
  )

  const loadAccount = useCallback(
    (acct: Account) => {
      const token = auth.token()
      if (!token) return expire()
      const mine = ++session.current
      setProfileStatus('loading')
      store.load(token).then(
        (stored) => onLoaded(acct, mine, stored),
        (e: unknown) => onLoadFailed(mine, e),
      )
    },
    [auth, store, expire, onLoaded, onLoadFailed],
  )

  // A returning visitor with a valid token: load their state once on start (status starts as "loading").
  const started = useRef(false)
  useEffect(() => {
    if (started.current) return
    started.current = true
    const acct = auth.current()
    const token = auth.token()
    if (!acct || !token) return
    const mine = ++session.current
    store.load(token).then(
      (stored) => onLoaded(acct, mine, stored),
      (e: unknown) => onLoadFailed(mine, e),
    )
  }, [auth, store, onLoaded, onLoadFailed])

  const retryLoad = useCallback(() => {
    if (account) loadAccount(account)
  }, [account, loadAccount])

  /** After any successful sign-in: load that account's saved state. */
  const startSession = useCallback(
    (result: AuthResult) => {
      if (result.ok) {
        setNotice(null)
        setAccount(result.account)
        setDemo(null)
        resetChat()
        loadAccount(result.account)
      }
      return result
    },
    [loadAccount, resetChat],
  )

  const signUp = useCallback<AppState['signUp']>(
    async (name, email, password) => startSession(await auth.signUp(name, email, password)),
    [auth, startSession],
  )

  const logIn = useCallback<AppState['logIn']>(
    async (email, password) => startSession(await auth.logIn(email, password)),
    [auth, startSession],
  )

  const signInWithGoogle = useCallback<AppState['signInWithGoogle']>(
    async (credential) => startSession(await auth.signInWithGoogle(credential)),
    [auth, startSession],
  )

  const resetPassword = useCallback<AppState['resetPassword']>(
    async (token, password) => startSession(await auth.resetPassword(token, password)),
    [auth, startSession],
  )

  const deleteAccount = useCallback<AppState['deleteAccount']>(
    async (password) => {
      const result = await auth.deleteAccount(password)
      if (result.ok) {
        auth.forget()
        clearSession()
        resetChat()
        setNotice('Your account and saved answers were deleted.')
      }
      return result
    },
    [auth, clearSession, resetChat],
  )

  /** "Sign out", or "Exit example" in example mode (which returns a signed-in user to their own data). */
  const leave = useCallback(() => {
    if (demo === null) {
      // Finish sending the last change before the token is revoked, so it isn't lost.
      const token = auth.token()
      const pending = inflight.current
      const last = queued.current
      clearSession()
      auth.forget()
      void (async () => {
        await pending?.catch(() => undefined)
        if (token && last) await store.save(token, last).catch(() => undefined)
        if (token) await auth.revoke(token)
      })()
    }
    setDemo(null)
    setDemoSteps({})
    resetChat()
  }, [auth, store, demo, clearSession, resetChat])

  const enterExample = useCallback(() => {
    setDemo(structuredClone(EXAMPLE))
    setDemoSteps({})
    resetChat()
  }, [resetChat])

  const persist = useCallback(
    (next: SavedProfile) => update((s) => ({ ...s, saved: { ...next, updated: Date.now() } })),
    [update],
  )

  const addLog = useCallback(
    (texts: string[]) => {
      const now = Date.now()
      update((s) => ({ ...s, log: [...texts.map((text) => ({ at: now, text })).reverse(), ...s.log].slice(0, MAX_LOG) }))
    },
    [update],
  )

  const confirmProfile = useCallback(() => {
    if (!dataRef.current.saved.confirmed) addLog(['Created your profile in the onboarding chat'])
    persist({ ...dataRef.current.saved, confirmed: true })
  }, [persist, addLog])

  const saveInfo = useCallback<AppState['saveInfo']>(
    (next, changes, policyChosen = []) => {
      if (demo !== null) setDemo(next)
      else {
        addLog(changes)
        // Coverage-type questions only count as answered once the person picks an answer, so a
        // profile from before those questions never gets defaults treated as real answers.
        const asked = FLOW.map((f) => f.k).filter((k) => !isPolicyField(k))
        const current = dataRef.current.saved
        persist({ ...current, p: next, known: [...new Set([...current.known, ...asked, ...policyChosen])] })
      }
      resetChat()
    },
    [demo, persist, addLog, resetChat],
  )

  const markPolicySeen = useCallback(
    (type: PolicyType) => {
      if (demo === null) update((s) => ({ ...s, policySeen: type }))
    },
    [demo, update],
  )

  const toggleStep = useCallback(
    (text: string, checked: boolean) => {
      if (demo !== null) setDemoSteps((prev) => ({ ...prev, [text]: checked }))
      else update((s) => ({ ...s, steps: { ...s.steps, [text]: checked } }))
    },
    [demo, update],
  )

  /* Chat tab: send the conversation to the backend, stream the reply, or fall back to canned answers. */
  const askChat = useCallback(
    async (question: string) => {
      const q = question.trim()
      if (!q || chatBusy) return
      const myEpoch = epoch.current
      const bubbleId = msgId()
      const setBubble = (patch: Partial<ChatMessage>) =>
        setChat((m) => m.map((x) => (x.id === bubbleId ? { ...x, ...patch } : x)))
      setChatBusy(true)
      setChat((m) => [...m, { id: msgId(), role: 'user', text: q }, { id: bubbleId, role: 'assistant', text: 'Thinking…' }])
      turns.current = [...turns.current, { role: 'user', content: q }]

      const { profile: p, demo: isDemo, known } = latest.current
      const canned = (note = "Standard answer. Live answers aren't available in this view.") => {
        setBubble({ text: fallbackAnswer(q, p), note })
        turns.current = turns.current.slice(0, -1)
      }
      // Unanswered coverage-type questions are left out, so the server treats them as unanswered
      // rather than as default answers. The example profile has them all.
      const unanswered = isDemo ? [] : POLICY_FIELDS.filter((f) => !known.includes(f))
      const context: ChatContext = {
        profile: Object.fromEntries(Object.entries(p).filter(([k]) => !(unanswered as string[]).includes(k))) as ChatContext['profile'],
        example: isDemo,
      }

      let partial = ''
      try {
        const text = await ai.chat(turns.current, context, (t) => {
          partial = t
          if (epoch.current === myEpoch) setBubble({ text: t })
        })
        if (epoch.current === myEpoch) turns.current = [...turns.current, { role: 'assistant', content: text }]
      } catch (e) {
        if (epoch.current !== myEpoch) return
        const code = e instanceof ChatError ? e.code : 'failed'
        if (code === 'unavailable') canned()
        else if (code === 'unverified')
          canned("Standard answer. The live answer's numbers didn't match your estimate, so it wasn't shown.")
        else if (code === 'timeout') canned('Standard answer. The live answer took too long.')
        else {
          turns.current = turns.current.slice(0, -1)
          const msg =
            code === 'rate_limited'
              ? "That's a lot of questions at once. Try again in a minute."
              : "I couldn't finish that answer. Try asking again."
          setBubble({ text: partial ? `${partial}\n\n${msg}` : msg })
        }
      } finally {
        if (epoch.current === myEpoch) setChatBusy(false)
      }
    },
    [chatBusy],
  )

  const value = useMemo<AppState>(
    () => ({
      account,
      isExample: demo !== null,
      profile,
      saved,
      log,
      steps,
      chat,
      chatBusy,
      profileStatus,
      retryLoad,
      saveFailed,
      notice,
      signUp,
      logIn,
      signInWithGoogle,
      requestPasswordReset: auth.requestPasswordReset,
      resetPassword,
      changePassword: auth.changePassword,
      deleteAccount,
      leave,
      enterExample,
      updateSaved: persist,
      confirmProfile,
      saveInfo,
      policySeen,
      markPolicySeen,
      toggleStep,
      askChat,
      resetChat,
    }),
    [
      account,
      demo,
      profile,
      saved,
      log,
      steps,
      chat,
      chatBusy,
      profileStatus,
      retryLoad,
      saveFailed,
      notice,
      signUp,
      logIn,
      signInWithGoogle,
      auth,
      resetPassword,
      deleteAccount,
      leave,
      enterExample,
      persist,
      confirmProfile,
      saveInfo,
      policySeen,
      markPolicySeen,
      toggleStep,
      askChat,
      resetChat,
    ],
  )

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}
