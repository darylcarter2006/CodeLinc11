import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { CallbackDialog } from '../components/CallbackDialog'
import { AskForm, ChatLog, Chips, type Bubble } from '../components/ChatLog'
import { fmt, short } from '../domain/format'
import { compute, laddering } from '../domain/needs'
import { useApp } from '../state/context'

/* Chat tab: free-form Q&A grounded in the saved coverage. A "Why?" link arrives as route state. */
export function ChatPage() {
  const { profile: p, isExample, account, chat, chatBusy, askChat, resetChat } = useApp()
  const location = useLocation()
  const navigate = useNavigate()
  const c = compute(p)
  const [helpOpen, setHelpOpen] = useState(false)

  // Ask a question handed over from the Breakdown tab once, then clear it so a reload doesn't re-ask.
  const handled = useRef<string | null>(null)
  const pending = (location.state as { ask?: string } | null)?.ask
  useEffect(() => {
    if (!pending || handled.current === location.key) return
    handled.current = location.key
    navigate('.', { replace: true, state: null })
    void askChat(pending)
  }, [pending, location.key, navigate, askChat])

  const opening: Bubble = {
    id: 'opening',
    role: 'assistant',
    content: `Hi${isExample ? '' : ' ' + (account?.name ?? '')}. I can answer questions using ${isExample ? "Maya's example" : 'your'} coverage: ${short(c.existing)} in place today${p.group ? `, including ${short(p.group)} through work` : ''}, against an estimated need of ${short(c.total)}. What would you like to know?`,
  }
  const messages: Bubble[] = [opening, ...chat.map((m) => ({ id: m.id, role: m.role, content: m.text, note: m.note }))]

  const suggestions = [
    ...(p.group ? [`What happens to my ${short(p.group)} work coverage if I change jobs?`] : []),
    `How does ${short(c.existing)} compare with the estimate?`,
    'Term or whole life for me?',
    ...(laddering(p, c) ? ['How would two policies compare?'] : []),
    ...(p.savings ? ['What changes if I count my savings?'] : []),
  ]

  return (
    <>
      <div className="view-head">
        <div>
          <div className="eyebrow">Chat</div>
          <h2>Ask about your coverage</h2>
        </div>
      </div>
      <div className="chat-layout">
        <aside className="card pad ctx" aria-label="What the assistant knows">
          <div className="eyebrow">{isExample ? 'Using example data' : 'Using your saved info'}</div>
          <h3>What I know about your coverage</h3>
          <dl className="kv">
            <dt>Through work</dt>
            <dd>{fmt(p.group)}</dd>
            <dt>Policies you own</dt>
            <dd>{fmt(p.policies)}</dd>
            <dt>Savings counted</dt>
            <dd>{fmt(p.savings)}</dd>
            <dt className="teal-text strong">In place</dt>
            <dd className="teal-text">{fmt(c.existing)}</dd>
            <dt>Estimated need</dt>
            <dd>{fmt(c.total)}</dd>
            <dt className="accent strong">Left to cover</dt>
            <dd className="accent">{fmt(c.gap)}</dd>
            <dt>Term that matches your needs</dt>
            <dd>{c.term} years</dd>
          </dl>
          <p className="muted small flush">
            Something wrong or changed?{' '}
            <Link className="linkish small" to="/info">
              Edit my info
            </Link>
          </p>
        </aside>
        <section className="card chat-full" aria-label="Chat">
          <div className="chat-head">
            <h2>Coverage assistant</h2>
            <button className="linkish" type="button" onClick={resetChat}>
              New chat
            </button>
          </div>
          <ChatLog messages={messages} label="Chat messages" />
          <div className="dock">
            <AskForm placeholder="Ask anything about your coverage" label="Ask a question" button="Ask" disabled={chatBusy} onSend={askChat} />
            <Chips items={suggestions} onPick={askChat} disabled={chatBusy} />
            <p className="human-help">
              Not finding what you need?{' '}
              <button className="linkish" type="button" onClick={() => setHelpOpen(true)}>
                Talk to a licensed Lincoln Financial representative
              </button>
            </p>
          </div>
        </section>
      </div>
      {helpOpen && (
        <CallbackDialog
          onClose={() => setHelpOpen(false)}
          defaultName={isExample ? '' : (account?.name ?? '')}
          defaultEmail={isExample ? '' : (account?.email ?? '')}
          summary={{
            estimate: { total: c.total, existing: c.existing, gap: c.gap, suggested: c.suggested, termYears: c.term },
            recentQuestions: chat.filter((m) => m.role === 'user').slice(-5).map((m) => m.text),
          }}
        />
      )}
    </>
  )
}
