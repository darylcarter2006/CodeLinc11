import { HttpError, postJson } from './http'

/*
 * Requests for a licensed professional to follow up. Behind an interface so the team can route
 * them to a CRM, inbox or scheduling tool later. Nothing pretends to be a live person.
 */

export type ContactMethod = 'email' | 'phone'
export type BestTime = 'morning' | 'afternoon' | 'evening' | 'any'

export interface CallbackRequest {
  name: string
  contactMethod: ContactMethod
  contact: string
  bestTime: BestTime
  /** What they want help with, in their own words. */
  topic: string
  /** Only present when the user chose to share it. */
  summary?: {
    estimate: { total: number; existing: number; gap: number; suggested: number; termYears: number }
    recentQuestions: string[]
  }
}

export type CallbackResult = { ok: true } | { ok: false; reason: 'unavailable' | 'invalid' | 'failed' }

export interface SupportService {
  requestCallback(req: CallbackRequest): Promise<CallbackResult>
}

// 404/501: endpoint not deployed yet. 503: no destination configured. 0: backend unreachable.
const UNAVAILABLE = [0, 404, 501, 503]

export const httpSupport: SupportService = {
  async requestCallback(req) {
    try {
      await postJson('/support/callback-requests', req)
      return { ok: true }
    } catch (e) {
      const status = e instanceof HttpError ? e.status : -1
      if (UNAVAILABLE.includes(status)) return { ok: false, reason: 'unavailable' }
      if (status === 422) return { ok: false, reason: 'invalid' }
      return { ok: false, reason: 'failed' }
    }
  },
}
