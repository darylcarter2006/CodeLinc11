# Frontend: Coverage Compass

React + TypeScript (Vite) client for Coverage Compass, the conversational life insurance needs
analyzer. The spec is [../docs/coverage-compass/HANDOFF.md](../docs/coverage-compass/HANDOFF.md),
with a visual reference in `prototype.html` and colors/type in `design-tokens.json`.

## Quick start

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

The app works fully without the backend: sign-up, profile and change log live in this browser,
onboarding uses the local parser, and Chat uses standard answers. When the backend's AI endpoints
exist (below), live answers turn on with no frontend change. In dev, Vite proxies `/v1/*` to
`http://localhost:8000`; override with `API_PROXY_TARGET=http://localhost:8001 npm run dev`.

## Checks (the same ones CI runs)

```bash
npm run lint
npm test             # vitest: calculator, parser, and a full sign-up → dashboard flow
npm run build        # tsc -b && vite build
```

## Ground rules this code follows

- **The math is deterministic code** in `src/domain/needs.ts`. The AI never computes a number;
  it only pulls fields out of free text and explains the math.
- **No model keys or prompts in the browser.** The frontend calls backend endpoints; the server
  owns the system prompts.
- **Auth and storage sit behind interfaces** (`services/auth.ts`, `services/profileStore.ts`).
  The current implementations use `localStorage` and never store passwords.
- Light theme only. Money uses full dollars wherever it's explained, compact ($1.43M) on tiles.

## Google sign-in

The sign-up / log-in card has a **Sign up with Google** / **Sign in with Google** button (one button
does both: a new Google email creates an account, a known one logs in). It uses Google Identity
Services and needs an OAuth client ID:

1. In [Google Cloud Console](https://console.cloud.google.com/apis/credentials), create an
   **OAuth client ID** of type **Web application**.
2. Under **Authorized JavaScript origins**, add `http://localhost:5173` (and the deployed URL later).
3. Put the ID in `frontend/.env.local`: `VITE_GOOGLE_CLIENT_ID=1234-abc.apps.googleusercontent.com`
4. Restart `npm run dev`.

Without a client ID the button still shows, and explains that Google sign-in isn't set up yet.

**With the backend running**, the token goes to `POST /v1/auth/google`, which verifies Google's
signature (plus audience, issuer, expiry and verified email), creates or finds the user, and
returns an account token. That token is stored in this browser and revoked on sign-out. The backend
needs the same client ID in `backend/.env` as `GOOGLE_CLIENT_ID`; see
[../backend/docs/google-oauth-setup.md](../backend/docs/google-oauth-setup.md).

**Without a backend** (404, unreachable, or the backend has no client ID), the browser falls back to
reading the token's name and email itself (checking issuer, audience, expiry and verified email,
but **not** the signature). That creates a browser-only account, just like the email form, and is
never trusted by the server. If the backend actively rejects a token (401), there is no fallback.

## Deploying to AWS Amplify

The build is defined in [`../amplify.yml`](../amplify.yml) (repo root): Node 22, `npm ci`,
`npm run build`, publishing `frontend/dist`. Someone with access to the team's AWS account and
admin rights on the GitHub repo does this once:

1. **AWS Console → Amplify → Create new app → GitHub.** Authorize Amplify, pick
   `darylcarter2006/CodeLinc11` and the `main` branch.
2. Tick **"My app is a monorepo"** and set the app root to **`frontend`**. Amplify picks up
   `amplify.yml` automatically.
3. Under **Environment variables**, add:
   - `VITE_API_BASE_URL`: the deployed backend's URL, e.g. `https://api.example.com`
     (no trailing slash). Leave it unset until the backend is deployed; the app still works
     with the local parser and standard answers.
   - `VITE_GOOGLE_CLIENT_ID`: the Google OAuth client ID (see "Google sign-in").
4. **Save and deploy.**
5. **Hosting → Rewrites and redirects → Manage redirects → Open text editor**, paste the
   contents of [`amplify-rewrites.json`](amplify-rewrites.json), and save. This makes links like
   `/dashboard` work on refresh. It deliberately skips `/v1/...`, so API calls are never answered
   with the app's HTML.
6. After the first deploy, copy the app's URL (`https://main.<id>.amplifyapp.com`) and:
   - add it to the Google OAuth client's **Authorized JavaScript origins**;
   - set the backend's `CORS_ORIGINS` to it (only needed when `VITE_API_BASE_URL` points to a
     backend on another domain).

Every push to `main` redeploys. `VITE_*` values are baked in at build time, so redeploy after
changing them. Never put secrets in them: they end up in the public JavaScript.

## Backend AI contract (to be built on the FastAPI side)

Both endpoints should return **503** when no model is configured. The frontend treats 404, 501,
503 and network errors as "AI unavailable" and falls back for the rest of the page session.

### `POST /v1/ai/extract`

Request:

```json
{ "askedField": "income", "question": "What's your yearly income before taxes? ...",
  "profile": { "deps": ["partner"], "income": 0, "...": "..." }, "message": "about 85k" }
```

Response (validate on the server with the same rules as `clean()` in `src/domain/parse.ts`; the
client validates again):

```json
{ "updates": { "income": 85000 }, "ack": "Thanks, noted.", "answer": "" }
```

Use the extraction prompt in the handoff (section "Extraction endpoint contract"). A fast,
low-cost model tier is fine.

### `POST /v1/ai/chat`

Request: the last 8 turns plus the data the server needs to build the standing instruction from
the handoff (section 6):

```json
{
  "messages": [{ "role": "user", "content": "Term or whole life for me?" }],
  "context": {
    "profile": { "...": "..." },
    "calculation": { "lines": [["Income replacement", 1111500]], "total": 1584500,
                     "existing": 176000, "gap": 1408500, "suggested": 1425000, "term": 30 },
    "firstName": "Maya", "example": false
  }
}
```

Response: the answer as a streamed `text/plain` body (chunks are appended as they arrive).
Return **429** when rate limited; the UI shows "That's a lot of questions at once."

## Explanations for terms and numbers

- **Insurance terms** (term life, whole life, cash value, laddering, group life, final expenses and
  more) have a dotted underline in tradeoff cards, coverage sources and the Breakdown table. Hover,
  tab to or tap one to see a plain-language definition. Definitions live in
  `src/domain/glossary.ts`; add a term there and it's picked up automatically.
- **Key numbers** on the Dashboard tiles and the Breakdown headline have a small **i** button that
  shows how the number was worked out with the person's own values (`src/domain/explain.ts`).

Both use `components/Tip.tsx`: it opens on hover, keyboard focus or tap, closes on Escape, and is
positioned to stay on screen on phones. Terms aren't added inside checkbox labels (the Next steps
list), since a button inside a label is confusing for keyboard and screen-reader users.

## Talk to a licensed Lincoln Financial representative

The Chat tab has a **Talk to a licensed Lincoln Financial representative** link for users the assistant isn't helping.
It opens a short callback-request form (name, email or phone, best time, what they need help with,
and an opt-in summary of their estimate and recent questions). Nothing in the app pretends to be a
live agent: a person follows up later.

Requests go to `POST /v1/support/callback-requests` (not built yet). Until it exists, the form says
"Callback requests aren't connected yet, so nothing was sent." The front end treats 404, 501, 503
and network errors as not connected, 422 as invalid input, and anything else as a retryable failure.

Request body (`summary` appears only when the user ticks "Share my estimate..."):

```json
{
  "name": "Maya", "contactMethod": "email", "contact": "maya@example.com",
  "bestTime": "morning", "topic": "Should I count my work coverage?",
  "summary": {
    "estimate": { "total": 1584500, "existing": 176000, "gap": 1408500, "suggested": 1425000, "termYears": 30 },
    "recentQuestions": ["Term or whole life for me?"]
  }
}
```

`contactMethod` is `email` or `phone`; `bestTime` is `any`, `morning`, `afternoon` or `evening`;
`topic` is at most 1,000 characters. Respond **201** on success. Validate everything server-side,
reject anything that looks like an SSN or account number, and route requests to whoever staffs them
(an inbox, CRM or scheduling tool).

## Layout

See [FILE_GUIDE.md](FILE_GUIDE.md) for a description of every file.

```text
src/
  domain/      pure logic: profile model + question flow, compute(), tradeoffs, parser (+ tests)
  services/    auth, profileStore, ai (backend calls), fallback answers, storage, http
  state/       AppProvider (app-wide state) and useApp()
  components/  Layout (top bar), RouteGuard, ChatLog, StackedBar, TradeoffCards
  pages/       Auth, Onboarding, Dashboard, Breakdown, MyInfo, Chat
  test/        Vitest setup and the end-to-end flow test
```
