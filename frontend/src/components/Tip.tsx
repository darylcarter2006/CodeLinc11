import { useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from 'react'
import { GLOSSARY, findTerms } from '../domain/glossary'

const WIDTH = 280
const MARGIN = 8

interface TipProps {
  /** The visible trigger content. */
  children: ReactNode
  /** Tooltip text. */
  content: ReactNode
  className: string
  /** Accessible name when the trigger is only an icon. */
  label?: string
  testId?: string
}

/**
 * A small explanation that opens on hover, keyboard focus or tap, and closes on Escape, blur or
 * scroll. Positioned inside the viewport so it never causes sideways scrolling on phones.
 */
function Tip({ children, content, className, label, testId }: TipProps) {
  const id = useId()
  const trigger = useRef<HTMLButtonElement>(null)
  const [hover, setHover] = useState(false)
  const [focus, setFocus] = useState(false)
  const [pinned, setPinned] = useState(false)
  const [style, setStyle] = useState<CSSProperties>({})
  const open = hover || focus || pinned

  useEffect(() => {
    if (!open || !trigger.current) return
    const r = trigger.current.getBoundingClientRect()
    const width = Math.min(WIDTH, window.innerWidth - MARGIN * 2)
    const left = Math.min(Math.max(MARGIN, r.left + r.width / 2 - width / 2), window.innerWidth - width - MARGIN)
    setStyle({ left, top: r.bottom + 6, width })
    const close = () => {
      setHover(false)
      setPinned(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      close()
      setFocus(false)
    }
    window.addEventListener('scroll', close, true)
    document.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('scroll', close, true)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <>
      <button
        ref={trigger}
        type="button"
        className={className}
        aria-label={label}
        aria-describedby={id}
        data-testid={testId}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        onFocus={() => setFocus(true)}
        onBlur={() => {
          setFocus(false)
          setPinned(false)
        }}
        onClick={() => setPinned((p) => !p)}
      >
        {children}
      </button>
      <span id={id} role="tooltip" className="tip-pop" hidden={!open} style={style}>
        {content}
      </span>
    </>
  )
}

/** An insurance term with its definition, e.g. <Term id="laddering">laddered</Term>. */
export function Term({ id, children }: { id: string; children: ReactNode }) {
  const entry = GLOSSARY[id]
  return (
    <Tip
      className="gloss-term"
      content={
        <>
          <b>{entry.term}.</b> {entry.definition}
        </>
      }
    >
      {children}
    </Tip>
  )
}

/** Text with any glossary terms in it turned into <Term>s (first mention of each). */
export function WithTerms({ text }: { text: string }) {
  return (
    <>
      {findTerms(text).map((part, i) =>
        typeof part === 'string' ? (
          part
        ) : (
          <Term key={i} id={part.key}>
            {part.text}
          </Term>
        ),
      )}
    </>
  )
}

/** A small "i" button that explains how a number was worked out. */
export function NumberInfo({ label, explanation, testId }: { label: string; explanation: string; testId?: string }) {
  return (
    <Tip className="info" label={`How we got ${label}`} content={explanation} testId={testId}>
      <span aria-hidden>i</span>
    </Tip>
  )
}
