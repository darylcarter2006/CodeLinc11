import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useSession } from '../session/context'
import { QuestionInput } from './QuestionInput'

const MAX_CHARS = 2000 // MESSAGE_MAX_CHARS on the backend

export function ChatPanel() {
  const { state, messages, busy, sendMessage, turnsRemaining } = useSession()
  const [draft, setDraft] = useState('')
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length, state?.next_question?.field])

  const question = state?.next_question ?? null
  const outOfTurns = turnsRemaining === 0

  const onSubmit = (e: FormEvent) => {
    e.preventDefault()
    const text = draft.trim()
    if (!text) return
    setDraft('')
    void sendMessage(text)
  }

  return (
    <section className="panel chat-panel" aria-label="Conversation">
      <div className="chat-log" aria-live="polite">
        {messages.length === 0 && (
          <div className="message assistant">
            Hi! I'll ask a few questions about your household to estimate how much life insurance
            coverage you might need. You can type answers in your own words or use the form below.
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} className={`message ${m.role}`}>
            {m.content}
          </div>
        ))}
        {question && (
          <div className="message assistant question">
            <p>{question.text}</p>
            <QuestionInput key={`${question.field}-${state?.revision}`} question={question} />
          </div>
        )}
        {state && !question && (
          <div className="message assistant">
            All set. Every answer is in and confirmed. Your estimate is on the right, and you can edit any answer on the
            "My answers" page.
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form className="chat-input" onSubmit={onSubmit}>
        <input
          aria-label="Message"
          value={draft}
          maxLength={MAX_CHARS}
          disabled={busy || outOfTurns}
          placeholder={outOfTurns ? 'Message limit reached; edit answers directly instead' : 'Type your answer…'}
          onChange={(e) => setDraft(e.target.value)}
        />
        <button type="submit" disabled={busy || outOfTurns || draft.trim() === ''}>
          {busy ? '…' : 'Send'}
        </button>
      </form>
      {turnsRemaining !== null && turnsRemaining <= 5 && (
        <p className="muted small">{turnsRemaining} messages left in this session.</p>
      )}
    </section>
  )
}
