import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'

export interface Bubble {
  id: string
  role: 'user' | 'assistant'
  content: ReactNode
  note?: string
}

/** Scrolling message list. Announces new messages politely to screen readers. */
export function ChatLog({ messages, label }: { messages: Bubble[]; label: string }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = ref.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages])
  return (
    <div className="msgs" ref={ref} aria-live="polite" aria-label={label}>
      {messages.map((m) => (
        <div key={m.id} className={`b ${m.role === 'user' ? 'u' : 'a'}`}>
          {m.content}
          {m.note && <span className="src">{m.note}</span>}
        </div>
      ))}
    </div>
  )
}

export function Chips({ items, onPick, disabled }: { items: string[]; onPick: (t: string) => void; disabled?: boolean }) {
  if (!items.length) return null
  return (
    <div className="chips">
      {items.map((t) => (
        <button key={t} type="button" className="chip sm" disabled={disabled} onClick={() => onPick(t)}>
          {t}
        </button>
      ))}
    </div>
  )
}

/** Text input + submit button for a chat dock. */
export function AskForm(props: { placeholder: string; label: string; button: string; disabled: boolean; onSend: (t: string) => void }) {
  const [text, setText] = useState('')
  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (props.disabled || !text.trim()) return
    props.onSend(text)
    setText('')
  }
  return (
    <form className="ask" onSubmit={submit}>
      <input
        type="text"
        value={text}
        placeholder={props.placeholder}
        autoComplete="off"
        aria-label={props.label}
        onChange={(e) => setText(e.target.value)}
      />
      <button className="btn" type="submit" disabled={props.disabled}>
        {props.button}
      </button>
    </form>
  )
}
