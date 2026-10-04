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

/** Send a request and return the raw Response. Network failures become HttpError(0, "network_error"). */
export async function request(
  method: 'GET' | 'POST' | 'PUT' | 'DELETE',
  path: string,
  body: unknown,
  { signal, token }: RequestOptions = {},
): Promise<Response> {
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers.Authorization = `Bearer ${token}`
  let res: Response
  try {
    res = await fetch(`${API_BASE}/v1${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    })
  } catch {
    if (signal?.aborted && (signal.reason as { name?: string } | undefined)?.name === 'TimeoutError')
      throw new HttpError(0, 'timeout', 'The server took too long to answer.')
    throw new HttpError(0, 'network_error', 'Could not reach the server.')
  }
  if (!res.ok) {
    const data = (await res.json().catch(() => null)) as { error?: { code?: string; message?: string } } | null
    throw new HttpError(res.status, data?.error?.code ?? 'http_error', data?.error?.message ?? res.statusText)
  }
  // A static host's single-page-app fallback answers unknown paths with index.html and 200.
  // The API never returns HTML, so treat that as "endpoint not found".
  if (res.headers.get('Content-Type')?.includes('text/html'))
    throw new HttpError(404, 'not_found', 'The API is not available at this address.')
  return res
}

/** POST JSON and return the raw Response. */
export const postJson = (path: string, body: unknown, options: RequestOptions = {}): Promise<Response> =>
  request('POST', path, body, options)

/** Send a request and parse the JSON reply (null for an empty body such as 202/204). */
export async function requestJson<T>(method: 'GET' | 'POST' | 'PUT', path: string, body?: unknown, options?: RequestOptions): Promise<T | null> {
  const res = await request(method, path, body, options)
  const text = await res.text()
  if (!text) return null
  try {
    return JSON.parse(text) as T
  } catch {
    throw new HttpError(502, 'bad_response', 'The server sent an unexpected reply.')
  }
}
