import { startTransition, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AskForm, ChatLog, Chips, type Bubble } from '../components/ChatLog'
import { applyUpdates, clean, parseLocal } from '../domain/parse'
import { LABEL, neededSteps, nextStep, showVal, type SavedProfile } from '../domain/profile'
import { ai } from '../services/ai'
import { useApp } from '../state/context'

const MISSED = "I didn't quite catch that. Could you put it another way? A rough number is fine."

let nextId = 0
const id = () => `o${++nextId}`

/* Onboarding: one question at a time; AI extraction first, local parser as backstop; saves every answer. */
export function OnboardingPage() {
  const { account, saved, updateSaved, confirmProfile } = useApp()
  const navigate = useNavigate()
  const name = account?.name ?? ''
  const savedRef = useRef(saved)
  useEffect(() => {
    savedRef.current = saved
  }, [saved])

  // The conversation starts with a greeting and the first open question (or the summary when resuming at the end).
  const [messages, setMessages] = useState<Bubble[]>(() => [
    {
      id: id(),
      role: 'assistant',
      content:
        saved.known.length > 0
          ? `Welcome back, ${name}. Let's pick up where we left off.`
          : `Hi ${name}! I'll ask a few quick questions to size your coverage. Answer however feels natural, and I'll save as we go.`,
    },
    askFor(saved),
  ])
  const [chips, setChips] = useState<string[]>(() => nextStep(saved)?.chips?.(saved.p) ?? [])
  const [busy, setBusy] = useState(false)
  const done = !nextStep(saved)

  const send = async (raw: string) => {
    const text = raw.trim()
    const current = savedRef.current
    const step = nextStep(current)
    if (!text || busy || !step) return
    setBusy(true)
    setChips([])
    const bubbleId = id()
    setMessages((m) => [...m, { id: id(), role: 'user', content: text }, { id: bubbleId, role: 'assistant', content: '…' }])

    const result = await ai.extract({ askedField: step.k, question: step.q(current.p), profile: current.p, message: text })
    const updates = clean(result?.updates)
    if (!(step.k in updates)) Object.assign(updates, clean({ [step.k]: parseLocal(step.k, text, current.p) }))

    const setBubble = (content: string) => setMessages((m) => m.map((x) => (x.id === bubbleId ? { ...x, content } : x)))
    if (Object.keys(updates).length) {
      const next = applyUpdates(updates, current)
      updateSaved(next)
      savedRef.current = next
      setBubble([result?.ack || 'Got it, saved.', result?.answer].filter(Boolean).join(' '))
      setMessages((m) => [...m, askFor(next)])
      setChips(nextStep(next)?.chips?.(next.p) ?? [])
    } else {
      setBubble([result?.answer, MISSED].filter(Boolean).join('\n\n'))
      setChips(step.chips?.(current.p) ?? [])
    }
    setBusy(false)
  }

  // One transition so the confirmed profile and the new route commit together; otherwise the
  // onboarding guard sees the confirmed profile first and sends everyone to the dashboard.
  const finish = (to: '/dashboard' | '/info') => {
    startTransition(() => {
      confirmProfile()
      navigate(to)
    })
  }

  const steps = neededSteps(saved)
  const count = steps.filter((f) => saved.known.includes(f.k)).length

  return (
    <>
      <div className="view-head">
        <div>
          <div className="eyebrow">Getting to know you</div>
          <h2>Let's talk about your situation</h2>
        </div>
      </div>
      <div className="onb">
        <section className="card chat-full" aria-label="Onboarding conversation">
          <div className="chat-head">
            <h2>Coverage assistant</h2>
            <span className="eyebrow">
              {count} of {steps.length} saved
            </span>
          </div>
          <ChatLog messages={messages} label="Conversation" />
          <div className="dock">
            <AskForm placeholder="Type your answer in your own words" label="Your answer" button="Send" disabled={busy || done} onSend={send} />
            {done ? (
              <div className="chips">
                <button className="btn" type="button" onClick={() => finish('/dashboard')}>
                  Looks right, show my dashboard
                </button>
                <button className="btn ghost" type="button" onClick={() => finish('/info')}>
                  Change something
                </button>
              </div>
            ) : (
              <Chips items={chips} onPick={send} disabled={busy} />
            )}
          </div>
        </section>
        <aside className="card pad">
          <h3 className="side-title">Saved so far</h3>
          <div className="progress" aria-hidden>
            <span style={{ width: `${(count / steps.length) * 100}%` }} />
          </div>
          <SavedList saved={saved} showTodo />
          <p className="fine">You can change any of this later in My info.</p>
        </aside>
      </div>
    </>
  )
}

/** The next question bubble, or the end-of-onboarding summary when nothing is left to ask. */
function askFor(saved: SavedProfile): Bubble {
  const step = nextStep(saved)
  if (step) return { id: id(), role: 'assistant', content: step.q(saved.p) }
  return {
    id: id(),
    role: 'assistant',
    content: (
      <>
        That's everything I need. Here's what I saved:
        <div className="summary">
          <SavedList saved={saved} />
        </div>
        <span className="why">If anything is off, you can fix it now or any time in My info.</span>
      </>
    ),
  }
}

function SavedList({ saved, showTodo = false }: { saved: SavedProfile; showTodo?: boolean }) {
  return (
    <ul className="saved">
      {neededSteps(saved).map((f) =>
        saved.known.includes(f.k) ? (
          <li key={f.k}>
            <span>{LABEL[f.k]}</span>
            <span>{showVal(f.k, saved.p)}</span>
          </li>
        ) : showTodo ? (
          <li key={f.k} className="todo">
            <span>{LABEL[f.k]}</span>
            <span>Not yet</span>
          </li>
        ) : null,
      )}
    </ul>
  )
}
