import { HttpError, postJson } from './http'

/*
 * Backend side of Google sign-in. A "Sign in with Google" button hands us Google's signed ID
 * token (the "credential"); the backend verifies it and returns our own account token.
 */

export interface SignedInUser {
  id: string
  email: string
  name: string
  given_name: string | null
  picture: string | null
}

export interface SignInResult {
  access_token: string
  expires_at: string
  user: SignedInUser
}

/** Exchange Google's credential for our account token. Throws a readable Error. */
export async function exchangeCredential(credential: string): Promise<SignInResult> {
  try {
    const res = await postJson('/auth/google', { credential })
    return (await res.json()) as SignInResult
  } catch (e) {
    if (e instanceof HttpError) {
      if (e.status === 0) throw new Error("We couldn't reach the server. Check your connection and try again.")
      if (e.status === 503) throw new Error('Google sign-in is not available right now. Try again later.')
      if (e.status === 429) throw new Error('Too many sign-in attempts. Wait a minute and try again.')
    }
    throw new Error("Google sign-in couldn't be verified. Please try again.")
  }
}

/** Revoke the account token on the server. Best effort: sign-out continues locally regardless. */
export async function revokeToken(token: string): Promise<void> {
  try {
    await postJson('/auth/logout', {}, { token })
  } catch {
    // Already expired or offline: nothing else to do.
  }
}
