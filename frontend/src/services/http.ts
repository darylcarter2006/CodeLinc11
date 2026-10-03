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

export interface RequestOptions {
  signal?: AbortSignal
  /** Sent as "Authorization: Bearer <token>". */
  token?: string
}

/** POST JSON and return the raw Response. Network failures become HttpError(0, "network_error"). */
export async function postJson(path: string, body: unknown, { signal, token }: RequestOptions = {}): Promise<Response> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`
  let res: Response
  try {
    res = await fetch(`${API_BASE}/v1${path}`, {
      method: 'POST',
      headers,
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
