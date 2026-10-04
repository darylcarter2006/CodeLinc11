import type { Calculation } from '../domain/needs'
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

export interface ChatContext {
  /** Coverage-type answers are omitted until answered. */
  profile: Omit<Profile, PolicyField> & Partial<Pick<Profile, PolicyField>>
  calculation: Pick<Calculation, 'total' | 'existing' | 'gap' | 'suggested' | 'term'> & { lines: [string, number][] }
  firstName: string | null
  example: boolean
}

export type ChatErrorCode = 'unavailable' | 'rate_limited' | 'failed'

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

const markIfUnavailable = (e: unknown) => {
  if (e instanceof HttpError && UNAVAILABLE.includes(e.status)) available = false
}

export const ai = {
  isAvailable: () => available,

  /** Pull profile fields from free text. Returns null when AI can't help; the caller uses the local parser. */
  async extract(req: ExtractRequest): Promise<ExtractResult | null> {
    if (!available) return null
    try {
      const res = await postJson('/ai/extract', { ...req, message: req.message.slice(0, 500) })
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

  /** Stream a grounded answer. `onText` gets the full text so far. Throws ChatError. */
  async chat(messages: ChatTurn[], context: ChatContext, onText: (text: string) => void): Promise<string> {
    if (!available) throw new ChatError('unavailable')
    let res: Response
    try {
      res = await postJson('/ai/chat', { messages: messages.slice(-8), context })
    } catch (e) {
      markIfUnavailable(e)
      if (!available) throw new ChatError('unavailable')
      throw new ChatError(e instanceof HttpError && e.status === 429 ? 'rate_limited' : 'failed')
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
