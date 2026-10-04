import { useCallback, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { compute } from '../domain/needs'
import { EXAMPLE, FLOW, blankSaved, type Profile, type SavedProfile } from '../domain/profile'
import { ChatError, ai, type ChatContext, type ChatTurn } from '../services/ai'
import { localAuth, type Account, type AuthResult, type AuthService } from '../services/auth'
import { fallbackAnswer } from '../services/fallback'
import { localProfileStore, type ProfileStore, type StepsChecked } from '../services/profileStore'
import { AppContext, type AppState, type ChatMessage } from './context'

/*
 * App-wide state: who is signed in, example mode, the saved profile, change log, next-step checks
 * and the Chat tab conversation. Example mode works on an in-memory copy and never persists.
 */

interface Props {
  children: ReactNode
  auth?: AuthService
  store?: ProfileStore
}

let nextId = 0
const msgId = () => `m${++nextId}`

export function AppProvider({ children, auth = localAuth, store = localProfileStore }: Props) {
  const [account, setAccount] = useState<Account | null>(() => auth.current())
  const [saved, setSaved] = useState<SavedProfile>(() => (auth.current() ? store.loadProfile() : blankSaved()))
  const [log, setLog] = useState(() => store.loadLog())
  const [steps, setSteps] = useState<StepsChecked>(() => store.loadSteps())
  const [demo, setDemo] = useState<Profile | null>(null)
  const [chat, setChat] = useState<ChatMessage[]>([])
  const [chatBusy, setChatBusy] = useState(false)

  const profile = demo ?? saved.p
  const turns = useRef<ChatTurn[]>([])
  const epoch = useRef(0)
  // Latest values for async chat requests. Layout effect so it's current before any child effect asks.
  const latest = useRef({ profile, account, demo: demo !== null })
  useLayoutEffect(() => {
    latest.current = { profile, account, demo: demo !== null }
  }, [profile, account, demo])

  const persist = useCallback(
    (next: SavedProfile) => {
      const stamped = { ...next, updated: Date.now() }
      setSaved(stamped)
      store.saveProfile(stamped)
    },
    [store],
  )

  const addLog = useCallback(
    (texts: string[]) => {
      setLog((prev) => {
        const now = Date.now()
        const next = [...texts.map((text) => ({ at: now, text })).reverse(), ...prev]
        store.saveLog(next)
        return next
      })
    },
    [store],
  )

  const resetChat = useCallback(() => {
    epoch.current++
    turns.current = []
    setChat([])
    setChatBusy(false)
  }, [])

  const loadFromStore = useCallback(() => {
    setSaved(store.loadProfile())
    setLog(store.loadLog())
    setSteps(store.loadSteps())
  }, [store])

  /** After any successful sign-in: a new account starts a fresh profile, a returning one loads theirs. */
  const startSession = useCallback(
    (result: AuthResult) => {
      if (result.ok) {
        if (result.isNew) store.reset()
        loadFromStore()
        setAccount(result.account)
        setDemo(null)
        resetChat()
      }
      return result
    },
    [store, loadFromStore, resetChat],
  )

  const signUp = useCallback<AppState['signUp']>(
    (name, email, password) => startSession(auth.signUp(name, email, password)),
    [auth, startSession],
  )

  const logIn = useCallback<AppState['logIn']>((email, password) => startSession(auth.logIn(email, password)), [auth, startSession])

  // isNew (a different account than this browser last saw) starts a fresh profile, so one
  // person's saved answers are never shown to another.
  const signInWithGoogle = useCallback<AppState['signInWithGoogle']>(
    async (credential) => startSession(await auth.signInWithGoogle(credential)),
    [auth, startSession],
  )

  /** "Sign out", or "Exit example" in example mode (which returns a signed-in user to their own data). */
  const leave = useCallback(() => {
    if (demo === null) {
      auth.signOut()
      setAccount(null)
    }
    setDemo(null)
    setSteps(store.loadSteps())
    resetChat()
  }, [auth, store, demo, resetChat])

  const enterExample = useCallback(() => {
    setDemo(structuredClone(EXAMPLE))
    setSteps({})
    resetChat()
  }, [resetChat])

  const confirmProfile = useCallback(() => {
    if (!saved.confirmed) addLog(['Created your profile in the onboarding chat'])
    persist({ ...saved, confirmed: true })
  }, [saved, persist, addLog])

  const saveInfo = useCallback<AppState['saveInfo']>(
    (next, changes) => {
      if (demo !== null) setDemo(next)
      else {
        addLog(changes)
        persist({ ...saved, p: next, known: [...new Set([...saved.known, ...FLOW.map((f) => f.k)])] })
      }
      resetChat()
    },
    [demo, saved, persist, addLog, resetChat],
  )

  const toggleStep = useCallback(
    (text: string, checked: boolean) => {
      setSteps((prev) => {
        const next = { ...prev, [text]: checked }
        if (demo === null) store.saveSteps(next)
        return next
      })
    },
    [demo, store],
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

      const { profile: p, account: acct, demo: isDemo } = latest.current
      const canned = () => {
        setBubble({ text: fallbackAnswer(q, p), note: "Standard answer. Live answers aren't available in this view." })
        turns.current = turns.current.slice(0, -1)
      }
      const c = compute(p)
      const context: ChatContext = {
        profile: p,
        calculation: {
          lines: c.lines.map((l) => [l.label, l.amt]),
          total: c.total,
          existing: c.existing,
          gap: c.gap,
          suggested: c.suggested,
          term: c.term,
        },
        firstName: isDemo ? null : (acct?.name ?? null),
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
      signUp,
      logIn,
      signInWithGoogle,
      leave,
      enterExample,
      updateSaved: persist,
      confirmProfile,
      saveInfo,
      toggleStep,
      askChat,
      resetChat,
    }),
    [account, demo, profile, saved, log, steps, chat, chatBusy, signUp, logIn, signInWithGoogle, leave, enterExample, persist, confirmProfile, saveInfo, toggleStep, askChat, resetChat],
  )

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>
}
