/* Minimal backend HTTP helper. Empty base in dev: the Vite proxy forwards /v1 to FastAPI. */

const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

export class HttpError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'HttpError'
    this.status = status
    this.code = code
  }
}

/** POST JSON and return the raw Response. Network failures become HttpError(0, "network_error"). */
export async function postJson(path: string, body: unknown, signal?: AbortSignal): Promise<Response> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}/v1${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  } catch {
    throw new HttpError(0, 'network_error', 'Could not reach the server.')
  }
  if (!res.ok) {
    const data = (await res.json().catch(() => null)) as { error?: { code?: string; message?: string } } | null
    throw new HttpError(res.status, data?.error?.code ?? 'http_error', data?.error?.message ?? res.statusText)
  }
  return res
}
