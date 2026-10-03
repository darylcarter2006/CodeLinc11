# Google sign-in setup

How "Sign in with Google" works, and the values you need to fill in. Nothing in this guide is
committed to the repo: the client ID goes in local `.env` files and deployment settings.

## How it works

```text
Browser                         Google                     Our backend
  │  "Sign in with Google" ───────►│
  │◄──── credential (signed ID token)
  │  POST /v1/auth/google {credential} ──────────────────────►│ verify signature, audience,
  │                                                           │ expiry, issuer, verified email
  │◄──────────── {access_token, expires_at, user} ────────────│ create/update user in Postgres
  │  later: Authorization: Bearer <access_token>              │
```

- **No passwords:** we never see or store one.
- **No client secret:** this flow doesn't use one. If Google Cloud shows you a client secret
  (it starts with `GOCSPX-`), don't put it anywhere in this project.
- **Accounts:** a user is keyed by Google's stable account ID (`sub`), so changing the Gmail
  address doesn't create a second account.
- **Account token:** ours, valid for 7 days by default (`ACCOUNT_TOKEN_TTL_HOURS`). Only its
  SHA-256 hash is stored.

## 1. Create the OAuth client (Google Cloud Console, once)

1. Go to <https://console.cloud.google.com/>, then create a project (for example "Coverage
   Compass") or pick the team's existing one.
2. **APIs & Services → OAuth consent screen** (also labeled **Google Auth Platform →
   Branding**):
   - App name: `Coverage Compass`. Add a support email and a developer contact email.
   - Audience: **External**.
   - While the app is in **Testing**, only the Google accounts you add under **Test users**
     can sign in. Add every teammate and every judge account you'll demo with.
3. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type: **Web application**.
   - **Authorized JavaScript origins:** `http://localhost:5173`, plus the deployed frontend
     address once it exists (for example `https://main.xxxx.amplifyapp.com`).
   - **Authorized redirect URIs:** leave empty. The button flow doesn't redirect.
4. Copy the **Client ID**. It looks like `123456789012-abc123….apps.googleusercontent.com`.

## 2. Backend (`backend/.env`)

```dotenv
GOOGLE_CLIENT_ID=<paste the client ID>
# Optional: restrict to one Google Workspace domain
# GOOGLE_HOSTED_DOMAIN=example.com
```

Restart uvicorn. With the client ID unset, `POST /v1/auth/google` returns 503
`auth_unavailable` and everything else keeps working.

## 3. Database (once per database)

The `users` and `account_tokens` tables come from migration `0003`. From `backend/`:

```bash
set -a; source .env; set +a
.venv/bin/alembic upgrade head
.venv/bin/alembic current        # expect: 0003 (head)
```

Only one person needs to run this against RDS.

## 4. Frontend

The Sign in with Google button is already on the auth page (`frontend/src/components/GoogleButton.tsx`).
Give it the same client ID in `frontend/.env.local`:

```dotenv
VITE_GOOGLE_CLIENT_ID=<the same client ID>
```

Restart `npm run dev`. With the backend running, sign-in is verified by the server. Without it,
the button falls back to a browser-only account (see `frontend/README.md`, "Google sign-in").

## 5. Deployment

- **Backend:** set `GOOGLE_CLIENT_ID` in the backend service's environment (App Runner / ECS).
- **Frontend:** set `VITE_GOOGLE_CLIENT_ID` in the frontend build environment (Amplify).
- **Google Cloud:** add the deployed frontend URL to **Authorized JavaScript origins**.

## API reference

| Method | Path | Body / header | Result |
|---|---|---|---|
| POST | `/v1/auth/google` | `{"credential": "<Google ID token>"}` | `{access_token, expires_at, user}` |
| GET | `/v1/auth/me` | `Authorization: Bearer <access_token>` | `{id, email, name, given_name, picture}` |
| POST | `/v1/auth/logout` | `Authorization: Bearer <access_token>` | 204; the token stops working |

Errors use the usual envelope:

- `invalid_credential` 401: forged, expired, wrong app, or unverified email
- `unauthorized` / `session_expired` 401: missing, invalid or expired account token
- `rate_limited` 429: more than `AUTH_RATE_LIMIT_PER_MINUTE` sign-ins per minute from one IP
- `auth_unavailable` 503: no client ID configured
- `auth_provider_unreachable` 503: Google's signing keys couldn't be fetched

## Troubleshooting

- **"The given origin is not allowed for the given client ID"** in the browser console: add
  the exact origin, including the port, under **Authorized JavaScript origins**. Changes can
  take a few minutes to apply.
- **Error 403 `access_denied` from Google:** the app is in Testing and that account isn't a
  test user.
- **`invalid_credential` for a real sign-in:** the backend's `GOOGLE_CLIENT_ID` doesn't match
  the client ID the button used.
- **Startup error "GOOGLE_CLIENT_ID should look like …":** you pasted the client secret or a
  partial ID.
