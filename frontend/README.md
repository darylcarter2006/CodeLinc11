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

The browser reads the Google token for name and email only (checking issuer, audience, expiry and
verified email) and then discards it. **It does not verify the token's signature**, so this is
prototype-grade. When real accounts land, send the token to the backend and verify it there
before trusting it.

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

## Talk to a licensed professional

The Chat tab has a **Talk to a licensed professional** link for users the assistant isn't helping.
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

## Leftover files to delete

These belong to the earlier Planner UI, are no longer imported, and can be removed:
`src/api/`, `src/session/`, `src/utils/`, `src/pages/{HomePage,PlannerPage,ProfilePage,LearnPage,NotFoundPage}.tsx`,
and `src/components/{AssessmentPanel,ChatPanel,ExpenseEditor,QuestionInput}.tsx`.
