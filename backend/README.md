# Backend: life-insurance needs analyzer

FastAPI service that collects a household's goals through a guided conversation (or direct
edits), computes a coverage-gap **planning estimate** with a versioned, deterministic
calculator, and explains the result. It is not a quote engine or a product recommender.

The design is in [docs/blueprint.md](docs/blueprint.md). This README covers how to run the
code and the decisions made where the blueprint was open or contradictory.

## Quick start

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env            # optional; defaults work without it
.venv/bin/uvicorn app.main:app --reload
```

- API: http://localhost:8000/v1
- Interactive docs (OpenAPI): http://localhost:8000/docs (only when `ENV` is `local`, `test` or
  `dev`; a deployed service hides them)

You don't need a database or AWS credentials. Sessions are kept in memory, and a rule-based stub
stands in for the AI model. To use PostgreSQL (local Docker or RDS), see
[docs/database-setup.md](docs/database-setup.md).
To deploy to AWS (ECS Express Mode), see [docs/deploy-ecs.md](docs/deploy-ecs.md).

## Checks (the same ones CI runs)

```bash
.venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests
.venv/bin/mypy app tests                       # strict mode
.venv/bin/pytest --cov=app --cov-fail-under=90
docker build -t insurance-backend .

# API tests against PostgreSQL (needs a migrated database; see docs/database-setup.md)
REPOSITORY_BACKEND=postgres DATABASE_URL=postgresql+asyncpg://... .venv/bin/pytest tests/api
```

## Layout

```text
app/
  main.py            app factory: middleware, error handlers, routers
  container.py       wires repository + AI adapter + services (the only place adapters are chosen)
  settings.py        env-var config (pydantic-settings)
  errors.py          AppError subclasses -> stable error codes
  api/               thin HTTP routes: authorize, validate, call a service, return a contract
  contracts/         request/response models: the frontend contract
  domain/            profile, questions, assessment types, stored records (no framework imports)
  calculators/       CalculationPolicy interface, needs-v1, version registry (pure functions)
  services/          sessions, conversation turn, extraction validation, profile edits,
                     assessments/scenarios, explanation templates, presenters, idempotency
  repositories/      SessionRepository interface + in-memory and PostgreSQL implementations
  db/                SQLAlchemy models, async engine, Alembic migrations
  ai/                AIAdapter interface + deterministic stub
  content/           reviewed educational copy (pending compliance review)
  security/          token generation/hashing, Google ID-token verification, rate limiting, log redaction
  middleware/        request ID + body limit + access log; error envelope handlers
tests/
  unit/              calculator (golden fixtures), stub AI, extraction rules, domain
  api/               end-to-end HTTP behavior
  fixtures/          needs_v1_cases.json: golden calculator cases
```

## API (v1)

| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/health` | Liveness only |
| GET | `/v1/ready` | Readiness (session store reachable) |
| POST | `/v1/auth/signup` | Create an email and password account → account token (201) |
| POST | `/v1/auth/login` | Log in with email and password → account token |
| POST | `/v1/auth/google` | Sign in with a Google ID token → account token (see [docs/google-oauth-setup.md](docs/google-oauth-setup.md)) |
| GET | `/v1/auth/me` | The signed-in user (account token) |
| POST | `/v1/auth/password` | Change password (signed in); signs out other devices (204) |
| POST | `/v1/auth/password-reset/request` | Email a reset link if the address has an account; always 202 |
| POST | `/v1/auth/password-reset/confirm` | Set a new password from a reset link → account token |
| POST | `/v1/auth/logout` | Revoke the account token (204) |
| GET / PUT | `/v1/account/profile` | The signed-in person's saved answers, change log and checklist |
| DELETE | `/v1/account` | Delete the account and everything kept for it (password required if it has one) (204) |
| POST | `/v1/ai/extract` | Coverage Compass onboarding: pull profile fields from one answer |
| POST | `/v1/ai/chat` | Coverage Compass chat: streamed `text/plain` answer |
| POST | `/v1/support/callback-requests` | Ask a licensed representative to follow up (201) |

The original Planner session API below is **off by default** (`PLANNER_API_ENABLED=false`): the
current front end doesn't use it, and it lets anyone create database rows without signing in.
Turn it on only for local work on that API (the test suite turns it on).

| Method | Path | Purpose |
|---|---|---|
| POST | `/v1/sessions` | Create anonymous session → `session_id`, `access_token`, `expires_at` |
| GET | `/v1/sessions/{id}` | Profile, next question, live assessment, turn count |
| DELETE | `/v1/sessions/{id}` | Delete session and all its data (204) |
| POST | `/v1/sessions/{id}/token` | New token; old one invalidated; session extended |
| GET / PATCH | `/v1/sessions/{id}/profile` | Read / directly edit or confirm answers |
| GET / POST | `/v1/sessions/{id}/messages` | Chat history / submit a chat turn |
| POST | `/v1/sessions/{id}/assessments` | Save an immutable assessment (201) |
| GET | `/v1/sessions/{id}/assessments/latest` | Latest saved, with `is_current` / `stale_reason` |
| POST | `/v1/sessions/{id}/scenarios` | What-if overrides; nothing saved |
| GET | `/v1/content/coverage-types` | Term vs permanent education copy |

### Accounts

- **Passwords** are hashed with Argon2id (`app/security/passwords.py`, OWASP settings) and never
  logged or returned. Rules: 8 to 128 characters, not a very common password, not the email.
  Emails are trimmed and lowercased, and unique across accounts.
- **Log-in** gives one answer for a wrong email or a wrong password, and takes as long either way.
  Limits: `AUTH_RATE_LIMIT_PER_MINUTE` per IP (10) and `LOGIN_ATTEMPTS_PER_EMAIL` per address
  (10 per 15 minutes).
- **Account tokens** are 32 random bytes; only their SHA-256 hash is stored. They last
  `ACCOUNT_TOKEN_TTL_HOURS` (168). Changing or resetting a password revokes the others.
- **Password reset** (`EMAIL_PROVIDER=ses`, see [docs/deploy-ecs.md](docs/deploy-ecs.md) step 10):
  a single-use link valid for 30 minutes, stored as a hash. The request always answers 202 and
  sends in the background, so it never reveals whether an address has an account. Locally,
  `EMAIL_PROVIDER=outbox` with `APP_BASE_URL=http://localhost:5173` prints the email to the
  console instead (refused outside local/test/dev).
- **Google and passwords on one email:** signing in with Google links to the account with the same
  email. If that account's password was set by someone who never proved they own the address
  (no reset link used yet), Google sign-in removes that password and signs out its sessions.
  A Google-only account adds a password through "Forgot password?".
- **Deleting and expiry** ([docs/data-handling.md](../docs/data-handling.md)): `DELETE /v1/account`
  removes the account, its saved answers, tokens, reset links and callback requests. Each server
  also deletes accounts unused for `ACCOUNT_RETENTION_DAYS` (180), callback requests older than
  `CALLBACK_RETENTION_DAYS` (30), and expired tokens, at start-up and every
  `RETENTION_SWEEP_HOURS` (6).
- **Saved state** (`/v1/account/profile`) is validated field by field (same bounds as the AI
  endpoints), capped at 50 log entries and 20 checklist items, and only ever readable with that
  account's token.

### Callback requests

`POST /v1/support/callback-requests` backs the front end's "Talk to a licensed Lincoln Financial
representative" form (contract in `app/contracts/support.py`). Signing in is optional; with a
valid account token the request is linked to the account. Requests are stored in
`callback_requests` (migration 0004). The server rejects anything that looks like a Social
Security number or a 10+ digit account or card number, checks that the contact matches the
chosen method, and never logs the contact details. Limits: `SUPPORT_RATE_LIMIT_PER_HOUR` per
client IP (default 5) and `SUPPORT_GLOBAL_RATE_LIMIT_PER_HOUR` across everyone (default 200).

### Serving the front end too

With `STATIC_DIR` set to a built front end (`frontend/dist`), this server also serves the app's
pages and files, so one container runs everything (the [root Dockerfile](../Dockerfile)). API
paths are never answered with the page. On AWS this is unset: Amplify serves the front end.

### Security headers

Every response carries `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Cache-Control: no-store`, `Referrer-Policy: no-referrer` and a `default-src 'none'`
Content-Security-Policy (`app/middleware/security_headers.py`). With `ENV=demo` or `prod` it
also sends HSTS. The front end's headers are in `customHttp.yml` at the repo root (Amplify).

### Coverage Compass AI endpoints

These follow the contract in [../frontend/README.md](../frontend/README.md) ("Backend AI
contract"), including its camelCase field names. They need no session or token, because the
frontend calls them before an account exists, so they are rate limited per client IP
(`AI_RATE_LIMIT_PER_MINUTE`, default 20).

- **Provider:** Claude through the Anthropic API (`app/ai/claude.py`, official `anthropic`
  SDK) when `AI_PROVIDER=anthropic` and `ANTHROPIC_API_KEY` are set; Claude Sonnet
  (`claude-sonnet-5-5`) for both extraction and chat by default, adaptive thinking at `low`
  effort, and server-side refusal fallbacks on. Override with `AI_MODEL_FAST`,
  `AI_MODEL_SMART`, `AI_EFFORT` and `AI_REFUSAL_FALLBACKS`. The app refuses to start if
  `AI_PROVIDER=anthropic` has no key. A refusal from Claude is treated as a failure, never
  shown as an answer. A bad key or unknown model returns 503 (the front end falls back); rate
  limits return 429; other errors return 502 (chat) or empty fields (extraction).
- **No model configured (`AI_PROVIDER=stub`, the default):** both return **503** `ai_unavailable`. The
  frontend then uses its local parser and standard answers.
- **Extract:** the prompt is built on the server from the handoff. The model's `updates` pass
  through `clean()` in `app/domain/compass.py`, a port of the frontend's validator. A link in
  `ack`/`answer` is dropped. Unusable output returns empty fields, so the frontend's parser
  takes over.
- **Figures are checked before they're shown** ([app/domain/figures.py](app/domain/figures.py)):
  the chat answer is collected in full (within 60 seconds), and every dollar amount in it must
  match an amount the server's own calculation produced for this profile, or one the person
  typed. Otherwise the reply is `502 ai_unverified` and the front end shows a standard answer and
  says why. Onboarding acknowledgements with an unchecked figure are dropped the same way.
- **Chat:** the numbers in the standing instruction are **recomputed on the server** with
  `compute()` (a port of `frontend/src/domain/needs.ts`, tested against the handoff vectors).
  The browser's `calculation` field is ignored. Errors before the first chunk return
  429/502/503; after that, the stream just ends.
- **Provider throttling** returns 429 `rate_limited`.

Every session endpoint requires `Authorization: Bearer <access_token>`. Writes (`messages`,
`PATCH profile`) require `expected_revision` and a `client_request_id`. Retrying with the
same ID replays the original response.

## Contract decisions

These settle the open items from the blueprint audit. Change them deliberately, because the
frontend depends on them.

1. **Line items.** These six codes are always present, in this order:
   1. `ongoing_support`
   2. `one_time_expenses`
   3. `available_assets`
   4. `personal_coverage`
   5. `employer_coverage`
   6. `additional_gap`

   Offsets use the amount *applied*, capped at the need still remaining, so rows 1–5 always
   sum to row 6. Offsets also carry the user's `entered_amount`. `raw_gap` is internal and
   never returned.
2. **Status and required fields.**
   - **`incomplete`:** `annual_support_need`, `annual_survivor_contribution` or `support_years`
     is missing or unknown. No numbers are returned.
   - **`partial`:** numbers are returned, but something is unconfirmed, or an expense/offset
     field is unanswered or unknown (treated as $0 and listed in `unresolved_fields` and
     `assumptions`).
   - **`complete`:** every calculation input is known and confirmed.
3. **Coverage fields are flat.** The profile has `personal_coverage` and `employer_coverage`
   fields instead of an `existing_coverage` list. This is simpler for extraction, PATCH and
   provenance.
4. **Provenance.** Every answered field is `{value, source, confirmed}`.
   - A field that is `null` has not been asked yet.
   - `{"value": null}` means the user said "I don't know". Unknown is never treated as zero.
   - Chat-extracted values are `stated` and unconfirmed.
   - PATCH values are `edited` and confirmed.
   - PATCH `confirm: [...]` accepts existing values. During the review question, a plain
     "yes" also confirms them.
5. **Assessments are immutable.** `is_current` is derived by comparing the saved snapshot
   with the current profile, so chat turns that change nothing don't mark it stale. PATCH and
   chat return a live `assessment` preview. Only `POST /assessments` saves one.
6. **Scenarios** take up to 5 named override sets and return each result plus a `range`
   (min/max gap across base + scenarios; not a probability range).
7. **Errors** always use `{"error": {"code", "message", "request_id", ...}}`. Codes:
   - `validation_error` 422
   - `unauthorized` 401
   - `session_expired` 401
   - `not_found` 404, also returned for a valid token on someone else's session, so session
     IDs can't be probed
   - `stale_revision` 409, includes `current_revision`
   - `duplicate_request` 409
   - `payload_too_large` 413
   - `turn_limit_exceeded` 429
   - `internal_error` 500
8. **`next_question.input_type`** is `integer`, `currency`, `expenses` or `confirm`. The
   review step uses `field: "review"` and lists `review_fields`. `next_question` is `null`
   once everything is answered and confirmed.
9. **Idempotency** keys are scoped per session `(session_id, client_request_id)`, and a hash
   of the request is stored with each one.
10. **Chat replies never contain amounts.** The client renders numbers from `assessment`.
    Model-phrased questions that contain digits or links are replaced by approved copy.

## What's deliberately not built yet

Each item matches a step in blueprint §13. Its interface is already in place.

- **Postgres concurrency guard:** the Postgres repository is implemented (step 4), but
  `session_lock` is a no-op there. Two simultaneous retries can both call the model; one gets
  409 and its next retry replays. To close that gap, insert a *pending* idempotency record
  before the model call.
- **Income-estimation sub-flow:** needs `annual_income` and expense-share fields.
- **Assumption-flag questions:** the mortgage/education double-count flags can be set by
  PATCH, and the calculator warns about them, but the chat doesn't ask yet.
- **Rate limiting:** do this at the edge (WAF/App Runner) rather than in-process.
- **Verified resource links:** `content/catalog.py` has `RESOURCES` empty on purpose.
