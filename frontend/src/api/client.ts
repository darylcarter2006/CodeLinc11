import type {
  AssessmentResponse,
  CoverageTypesResponse,
  ErrorBody,
  MessageRequest,
  MessageResponse,
  MessagesResponse,
  ProfilePatchRequest,
  ProfileResponse,
  ScenarioRequest,
  ScenarioResponse,
  SessionCreatedResponse,
  SessionResponse,
  TokenResponse,
} from './types'

// Empty in local dev: requests go to /v1 and the Vite proxy forwards them to FastAPI.
const API_BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

/** Thrown for any non-2xx response. `code` is the backend's stable error code. */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly requestId: string | null
  readonly currentRevision: number | null

  constructor(status: number, body: ErrorBody) {
    super(body.message)
    this.name = 'ApiError'
    this.status = status
    this.code = body.code
    this.requestId = body.request_id
    this.currentRevision = body.current_revision ?? null
  }
}

/** Matches the backend's ClientRequestId pattern: 8-64 chars of [A-Za-z0-9_-]. */
export function newClientRequestId(): string {
  return crypto.randomUUID()
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  token?: string
}

async function request<T>(path: string, { method = 'GET', body, token }: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers['Authorization'] = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(`${API_BASE}/v1${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, {
      code: 'network_error',
      message: 'Could not reach the server. Check your connection and that the backend is running.',
      request_id: null,
    })
  }

  if (response.status === 204) return undefined as T

  const data: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const envelope = data as { error?: ErrorBody } | null
    throw new ApiError(
      response.status,
      envelope?.error ?? {
        code: 'internal_error',
        message: 'Something went wrong. Please try again.',
        request_id: response.headers.get('X-Request-ID'),
      },
    )
  }
  return data as T
}

const s = (id: string) => `/sessions/${encodeURIComponent(id)}`

export const api = {
  health: () => request<{ status: 'ok' | 'unavailable' }>('/health'),

  createSession: () => request<SessionCreatedResponse>('/sessions', { method: 'POST' }),
  getSession: (id: string, token: string) => request<SessionResponse>(s(id), { token }),
  deleteSession: (id: string, token: string) => request<void>(s(id), { method: 'DELETE', token }),
  refreshToken: (id: string, token: string) =>
    request<TokenResponse>(`${s(id)}/token`, { method: 'POST', token }),

  getProfile: (id: string, token: string) => request<ProfileResponse>(`${s(id)}/profile`, { token }),
  patchProfile: (id: string, token: string, body: ProfilePatchRequest) =>
    request<ProfileResponse>(`${s(id)}/profile`, { method: 'PATCH', token, body }),

  getMessages: (id: string, token: string) => request<MessagesResponse>(`${s(id)}/messages`, { token }),
  postMessage: (id: string, token: string, body: MessageRequest) =>
    request<MessageResponse>(`${s(id)}/messages`, { method: 'POST', token, body }),

  saveAssessment: (id: string, token: string, expectedRevision?: number) =>
    request<AssessmentResponse>(`${s(id)}/assessments`, {
      method: 'POST',
      token,
      body: expectedRevision === undefined ? {} : { expected_revision: expectedRevision },
    }),
  latestAssessment: (id: string, token: string) =>
    request<AssessmentResponse>(`${s(id)}/assessments/latest`, { token }),
  runScenarios: (id: string, token: string, body: ScenarioRequest) =>
    request<ScenarioResponse>(`${s(id)}/scenarios`, { method: 'POST', token, body }),

  coverageTypes: () => request<CoverageTypesResponse>('/content/coverage-types'),
}
