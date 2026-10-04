import type { Field, PolicyField, Profile } from '../domain/profile'
import { HttpError, postJson } from './http'

/*
 * Backend AI endpoints. The browser never holds model keys or builds the system prompt; the
 * server does. Any "unavailable" answer switches this tab to the local parser and canned answers.
 */

export interface ExtractRequest {
  askedField: Field
  question: string
  profile: Profile
  message: string
}

export interface ExtractResult {
  updates: unknown
  ack: string
  answer: string
}

export interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
}

/**
 * Only what the explanation needs: the profile numbers (the server recomputes the estimate from
 * them). Not the person's name, and not the browser's own figures.
 */
export interface ChatContext {
  /** Coverage-type answers are omitted until answered. */
  profile: Omit<Profile, PolicyField> & Partial<Pick<Profile, PolicyField>>
  example: boolean
}

/** unverified: the server's check found figures that don't match the estimate, so it sent none. */
export type ChatErrorCode = 'unavailable' | 'rate_limited' | 'failed' | 'timeout' | 'unverified'

export class ChatError extends Error {
  readonly code: ChatErrorCode
  constructor(code: ChatErrorCode) {
    super(code)
    this.code = code
  }
}

// 404/501: endpoint not deployed yet. 503: no model configured. 0: backend unreachable.
const UNAVAILABLE = [0, 404, 501, 503]
let available = true
// A little longer than the server's own limits (30 s to extract, 60 s for a checked chat answer).
const EXTRACT_TIMEOUT_MS = 35_000
const CHAT_TIMEOUT_MS = 70_000

const markIfUnavailable = (e: unknown) => {
  // A slow answer isn't a missing backend: keep trying live answers next time.
  if (e instanceof HttpError && UNAVAILABLE.includes(e.status) && e.code !== 'timeout') available = false
}

export const ai = {
  isAvailable: () => available,

  /** Pull profile fields from free text. Returns null when AI can't help; the caller uses the local parser. */
  async extract(req: ExtractRequest): Promise<ExtractResult | null> {
    if (!available) return null
    try {
      const res = await postJson('/ai/extract', { ...req, message: req.message.slice(0, 500) }, { signal: AbortSignal.timeout(EXTRACT_TIMEOUT_MS) })
      const data = (await res.json()) as Partial<ExtractResult> | null
      return {
        updates: data?.updates ?? {},
        ack: String(data?.ack ?? '').slice(0, 120),
        answer: String(data?.answer ?? '').slice(0, 400),
      }
    } catch (e) {
      markIfUnavailable(e)
      return null
    }
  },

  /** A grounded answer whose figures the server has checked. `onText` gets the text as it arrives. Throws ChatError. */
  async chat(messages: ChatTurn[], context: ChatContext, onText: (text: string) => void): Promise<string> {
    if (!available) throw new ChatError('unavailable')
    let res: Response
    try {
      res = await postJson('/ai/chat', { messages: messages.slice(-8), context }, { signal: AbortSignal.timeout(CHAT_TIMEOUT_MS) })
    } catch (e) {
      markIfUnavailable(e)
      if (!available) throw new ChatError('unavailable')
      const code = e instanceof HttpError ? e.code : ''
      throw new ChatError(
        code === 'timeout' ? 'timeout' : code === 'ai_unverified' ? 'unverified' : e instanceof HttpError && e.status === 429 ? 'rate_limited' : 'failed',
      )
    }
    if (!res.body) {
      const text = await res.text()
      onText(text)
      return text
    }
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let text = ''
    try {
      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        text += decoder.decode(value, { stream: true })
        onText(text)
      }
    } catch {
      throw new ChatError('failed')
    }
    return text
  },
}
