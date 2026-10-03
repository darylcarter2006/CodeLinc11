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
