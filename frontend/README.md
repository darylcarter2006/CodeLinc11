# Frontend: life-insurance needs analyzer

React + TypeScript (Vite) client for the FastAPI backend in [../backend](../backend).
The API contract it implements is in [../backend/README.md](../backend/README.md#contract-decisions).

## Quick start

```bash
# Terminal 1: backend on :8000 (see backend/README.md)
cd backend && .venv/bin/uvicorn app.main:app --reload     # Windows: .venv\Scripts\uvicorn

# Terminal 2: frontend on :5173
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. In dev, Vite proxies `/v1/*` to the backend, so no CORS setup is
needed. To point the proxy elsewhere (for example if port 8000 is taken):

```bash
API_PROXY_TARGET=http://localhost:8001 npm run dev
```

For a deployed build, set `VITE_API_BASE_URL` to the backend origin. See `.env.example`.
Never put secrets in `VITE_*` variables: they are bundled into public JavaScript. The browser
never talks to the database or Bedrock directly.

## Checks (the same ones CI runs)

```bash
npm run lint
npm run build        # tsc -b && vite build
```

## Layout

```text
src/
  api/
    types.ts         TypeScript mirror of backend/app/contracts (keep in sync)
    client.ts        fetch wrapper: bearer token, error envelope -> ApiError, endpoints
  session/
    SessionContext.tsx  creates/restores the anonymous session; revision + idempotency handling
    context.ts       context type and the useSession() hook
  components/
    Layout.tsx       header, nav, error banner, disclaimer footer
    ChatPanel.tsx    conversation + the server's next_question
    QuestionInput.tsx  typed control per next_question.input_type (integer/currency/expenses/confirm)
    ExpenseEditor.tsx  one-time expenses, one per category
    AssessmentPanel.tsx  live estimate: status, all six line items, assumptions, warnings
  pages/             Home, Planner (chat + estimate), My answers (edit/confirm), Learn
  utils/format.ts    money formatting, field labels
```

## Rules the UI follows

- **Numbers come from `assessment`, never from chat text.** Amounts are shown in full dollars
  (`$1,250,000`, not `$1.3M`), and every line item is shown so the total can be checked.
- **Unknown is not zero.** "I don't know" sends `null`, and the UI shows it as "Don't know".
- **Writes send `expected_revision` and a fresh `client_request_id`.** On `stale_revision` the
  client reloads the session and asks the user to retry. On `session_expired` it starts a new one.
- The session ID and token live in `sessionStorage`, so they clear when the tab closes.

## Not built yet

- **Dependent sub-profiles.** The backend profile only has `dependents_count` and
  `youngest_dependent_age`. Per-dependent records need a backend contract change first.
- **Saved user profiles / login.** Sessions are anonymous; reading preferences from an
  existing account needs auth and the Postgres repository.
- **Scenarios UI.** `api.runScenarios` is wired up but no screen uses it yet.
