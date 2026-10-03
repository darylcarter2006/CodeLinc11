# Life-insurance needs analyzer: backend blueprint

> **Status: partly superseded.** The product is now defined by the Coverage Compass handoff
> ([../../docs/coverage-compass/HANDOFF.md](../../docs/coverage-compass/HANDOFF.md)). This
> blueprint's question flow, profile fields and `needs-v1` calculator describe the earlier
> Planner design, which the current front end does not use (see issue #11). Its principles
> still apply: deterministic math, untrusted model output, privacy by default, and no
> product recommendations. So does its guidance on security and operations.

## 1. Scope and principles

Build a **planning tool**, not a quote engine, underwriting system, or automated product recommendation. The backend should collect a household's stated goals, estimate a coverage gap using a versioned, deterministic methodology, and explain the inputs and calculation in plain language. Term/permanent comparisons are educational. A qualified professional should review individual insurance decisions; obtain legal/compliance review before production use.

**Core rules**

1. The language model may ask questions, extract candidate facts, and draft explanations; it never calculates, modifies, or overrides the official result.
2. Every assessment is reproducible from its saved input snapshot and calculation-policy version.
3. No inferred field becomes a user-confirmed fact. Record whether values were stated, user-edited, or default assumptions.
4. The coverage gap, a suggested scenario range, policy price, and affordable coverage are distinct concepts. Do not calculate policy affordability without actual approved premium data.
5. All assumptions are visible and editable; keep privacy by default. Ask for aggregate amounts rather than account numbers, names, medical history, or other unnecessary data.
6. API contracts remain stable while conversation, storage, model provider, and calculation strategies can change.

## 2. Recommended architecture

```text
React client (S3 + CloudFront or Amplify)
   |
   | HTTPS + bearer token (Authorization header)
   v
FastAPI application (ECS Fargate or App Runner)
   |-- Request middleware: request ID injection, timing, payload size limit, error normalization
   |-- API routers and Pydantic request/response contracts
   |-- Session service / question planner
   |-- AI adapter: extract candidate facts + compose limited explanations
   |-- Profile validator + normalization
   |-- Assessment service / versioned deterministic calculator
   |-- Content catalog: approved educational copy and resource URLs
   |-- Session repository
   `-- Observability and guardrails
          |                    |
          v                    v
      PostgreSQL            Amazon Bedrock
    (RDS or Aurora)      (with guardrails config)
```

Run the FastAPI container behind an HTTPS entry point (AWS ALB or App Runner's built-in TLS). React is hosted separately on S3+CloudFront or Amplify. Development uses an in-memory repository and a stub AI adapter so no database or AWS credentials are needed to run calculator tests. In deployed environments, the database password must be stored in AWS Secrets Manager and injected at container startup — never as a plaintext env var. The Bedrock IAM task role is scoped to the approved model ARN only. Never expose credentials or call Bedrock directly from React.

**Suggested code layout**

```text
app/
  main.py                          # app factory, middleware registration, router inclusion
  middleware/
    request_id.py                  # inject X-Request-ID on every request and response
    timing.py                      # log request duration
    error_handler.py               # normalize all unhandled exceptions to the error envelope
  api/
    sessions.py
    messages.py
    profiles.py
    assessments.py
    content.py
  contracts/
    requests.py                    # typed Pydantic input models
    responses.py                   # typed Pydantic output models including ErrorResponse
  domain/
    profile.py
    assessment.py
    questions.py
    policies.py
  services/
    conversation.py
    extraction.py
    assessment.py
    explanation.py
  calculators/
    base.py                        # CalculationPolicy ABC
    v1.py                          # needs-v1 pure function
  repositories/
    base.py                        # SessionRepository ABC
    postgres.py                    # SQLAlchemy async implementation
    memory.py                      # in-memory impl for local dev and tests
  db/
    migrations/                    # Alembic migration scripts
    models.py                      # SQLAlchemy ORM table definitions
    session.py                     # async engine + get_db dependency
  ai/
    base.py                        # AIAdapter ABC
    bedrock.py
    stub.py                        # deterministic stub for CI and local dev
  content/
    approved_copy.py
    resources.py
  security/
    tokens.py                      # token generation, validation, expiry
    redaction.py                   # log-safe field filtering
  settings.py                      # pydantic-settings config; reads from env vars
  tests/
    unit/
    api/
    integration/
    fixtures/
Dockerfile
docker-compose.yml                 # local stack: FastAPI + PostgreSQL
alembic.ini
.github/workflows/ci.yml           # lint, typecheck, unit + API tests on every PR
```

Keep HTTP routes thin: authenticate/authorize, validate request, call a service, serialize a response. Domain models and calculators must not import FastAPI, Bedrock, or DynamoDB — this is what makes them independently testable.

## 3. Domain and data model

Prefer explicit, typed fields over a single unstructured JSON blob. Monetary values are nonnegative **integer USD dollars** in the public API for MVP; reject cents/decimals or explicitly convert at the boundary. In Python do arithmetic with integers or `Decimal`, not binary floats. If other currencies are added later, add explicit currency and exchange-rate rules rather than silently mixing them.

### Profile fields (MVP)

- `dependents_count`: nonnegative integer, optional.
- `youngest_dependent_age`: optional integer. Never derive a support horizon without showing and confirming the assumption.
- `annual_support_need`: annual household spending **that the user wants life coverage to support**, not automatically gross salary. Optional; if the user supplies income instead of spending, see the income estimation path in §5.
- `annual_survivor_contribution`: annual income or other continuing cash flow specifically available for the same support goal. Optional; clarify whether it continues for the entire selected horizon.
- `support_years`: nonnegative integer, optional, explicitly stated or editable assumption.
- `one_time_expenses`: labeled items such as final expenses, education, and a chosen debt payoff. Store each `{id, label, amount, category}`; no duplicate categories by default.
- `available_assets`: amount the user elects to apply toward these needs, not total savings by default.
- `existing_coverage`: separate records for `personal` and `employer` coverage; distinguish known amount from unknown, and optionally model employer coverage in an alternative scenario rather than assuming it is portable.
- `budget_monthly`: optional, **informational only** until there is a verified premium source.
- `assumption_flags`: e.g., whether mortgage payments are included in annual support need and whether outstanding mortgage principal is included in one-time obligations.

For each user-supplied scalar, store `{value, source: stated | edited | assumption, confirmed: boolean}` or equivalent metadata. Candidate values proposed by AI must not be silently treated as confirmed. Use `null` for unknown, not `0`: unknown coverage is not the same as no coverage.

### Main entities

- `Session`: random opaque ID, owner/anonymous access metadata, timestamps, expiry, `revision`, `status`, `profile`, `conversation_state`, `schema_version`, `turn_count`.
- `Message`: ID, session ID, `role` (`user` or `assistant`), text, timestamp, turn ID; never log full text in general application logs.
- `Assessment`: ID, session ID, created time, `profile_revision`, frozen input snapshot, `calculation_version`, line items, assumptions, warnings, scenario outputs, completion state.
- `ContentResource`: curated title, summary, verified URL, source owner, and content version; do not fabricate URLs.

### Example profile fragment

```json
{
  "annual_support_need": {"value": 80000, "source": "stated", "confirmed": true},
  "annual_survivor_contribution": {"value": 20000, "source": "stated", "confirmed": true},
  "support_years": {"value": 15, "source": "assumption", "confirmed": false},
  "one_time_expenses": [
    {"id": "education-1", "label": "Education", "category": "education", "amount": 50000}
  ],
  "available_assets": {"value": 30000, "source": "stated", "confirmed": true},
  "existing_coverage": [
    {"id": "personal-1", "kind": "personal", "amount": 100000},
    {"id": "employer-1", "kind": "employer", "amount": 150000}
  ],
  "assumption_flags": {
    "mortgage_payment_in_annual_support": true,
    "mortgage_balance_in_one_time_expenses": false
  }
}
```

If the user cannot provide `annual_support_need`, offer a *separately labeled* rough estimation method, but do not mix it with the spending-based calculator without showing the conversion assumptions. Future iterations can support varying contributions by year and discount rates behind a new calculation version.

## 4. Assessment calculation: clear, deterministic, versioned

A straightforward **v1 nominal-dollar model**:

```text
annual_shortfall = max(0, annual_support_need - annual_survivor_contribution)
ongoing_support_total = annual_shortfall * support_years
one_time_total = sum(eligible one_time_expenses)
assets_applied = min(available_assets, ongoing_support_total + one_time_total)
existing_coverage_applied = min(sum(existing_coverage amounts),
                                ongoing_support_total + one_time_total - assets_applied)
raw_gap = ongoing_support_total + one_time_total
          - available_assets - sum(existing_coverage amounts)
additional_coverage_gap = max(0, raw_gap)
```

`raw_gap` may be negative for internal analysis; the user-facing *additional coverage gap* never is. Return the actual totals used in the formula and explain that a zero gap under these inputs is **not** a guarantee that current coverage is sufficient. Do not describe `additional_coverage_gap` as the amount a person must buy.

**Avoid double counting:** If ongoing support spending includes mortgage payments, do not also add full mortgage payoff by default. The user may choose a payoff scenario, but then annual support must exclude the corresponding future mortgage payments; otherwise display a validation warning and ask for clarification. Similarly, do not add education both as annual household support and as a one-time education amount.

**Missing data:** Do not run a numeric final estimate with unknown critical inputs. Return `status: "incomplete"`, `missing_fields`, and a next question. Unknown optional deductions such as assets or existing coverage may be explicitly treated as zero **only if the user confirms that assumption**, otherwise give a labeled partial scenario, never an unqualified final gap. Values of zero provided by the user are valid.

**Range:** Do not invent a confidence interval. Create two or three transparent *scenarios*, such as 10, 15, and 20 years if those horizons fit the stated goals and the user agrees to use them. A displayed `low/high` is the min/max outputs under those named assumptions, not a probabilistic range. Return the base result and each scenario's modified inputs. If employer coverage is material, optionally add a side-by-side scenario with/without it; do not silently exclude it.

**Illustrative example:** $80,000 annual support need, $20,000 continuing contribution, 15 years, $50,000 education, $30,000 available assets, and $250,000 existing coverage results in $60,000 annual shortfall, $900,000 ongoing support, $950,000 before offsets, and **$670,000 additional coverage gap**. This is an illustrative estimate, not an insurance recommendation. Calculation: 60,000 × 15 + 50,000 − 30,000 − 250,000 = 670,000.

**Calculator API:** `calculate(profile, policy_version) -> AssessmentBreakdown`. Return line items with stable machine-readable codes, human-readable labels, and a `display_order` integer for consistent frontend rendering: `ongoing_support` (1), `one_time_expenses` (2), `available_assets` (3), `personal_coverage` (4), `employer_coverage` (5), `additional_gap` (6). Keep explanation copy separate from numeric computation. Use fixtures for zero income, unknown fields, zero/negative raw gap, employer coverage excluded, and corrected mortgage assumptions.

## 5. Conversation orchestration

A conversational interface is easiest to maintain when the backend owns the **question policy**, while the LLM handles flexible wording and extraction.

Suggested question order (skippable; adapt based on already known facts):

1. Does anyone depend on your financial support, and for how long would you want to support them?
2. Roughly how much household spending per year would need to continue?
   - **If the user knows their spending:** use it directly as `annual_support_need`.
   - **If the user knows their income but not spending:** enter the income estimation sub-flow — ask what share of that income covers household expenses, show the derived spending figure as an editable assumption labeled *"estimated from income"*, and set `source: "assumption"` with `confirmed: false` until the user accepts it. Do not silently equate gross income with support need.
3. Is there income that would continue toward those expenses?
4. Which one-time goals do you want to include: debt payoff, education, other family expenses?
5. How much existing personal and employer coverage do you have? Unknown is acceptable.
6. Would you like to count assets toward this goal? Ask about budget separately as an affordability preference, not a subtraction.
7. Show the extracted assumptions for review, then generate or refresh the assessment.

**One turn pipeline**

1. Authorize session; validate text length (max 2,000 chars), request size (max 16 KB), and idempotency key. Reject if `turn_count` exceeds the session limit (default 40; return `429` with a clear message).
2. Load current profile and a bounded window of recent messages (last 10 turns; do not send entire history to the model).
3. Ask the AI adapter for **candidate structured updates**, with field-level evidence from the user's latest message and a confidence/ambiguity flag. Treat returned JSON as untrusted and Pydantic-validate every field; never let the model create arbitrary profile keys.
4. Resolve contradictions: explicit user correction takes precedence; ambiguous answers become clarification questions, not automatic overwrites.
5. Merge valid, supported updates. Commit profile, message(s), and idempotency record atomically using a conditional revision write (see §7). Never write model-extracted facts against a stale revision.
6. Compute `missing_fields` and run the deterministic assessment if sufficiently complete.
7. Choose next question using backend rules. Optionally have the model phrase it clearly, but validate it for safety and length (max 500 chars); use approved fallback copy on AI failure.
8. Respond with the canonical profile, assessment status, `next_question` (structured), and `assistant_message` (conversational text). The client must render server-provided amounts, not numbers embedded in free-form AI text.

**AI boundary:** The AI may see only required profile fields and the bounded recent message window. The system prompt must instruct the model to ignore user text that attempts to override app rules, but the rule must also be enforced in code — do not rely solely on prompt instructions. Never execute model-suggested code or accept model-provided URLs as authoritative. Validate all structured outputs and reject unsupported keys, impossible numbers, out-of-range values, contradictory units, and percentages mistaken for dollar amounts. If the model is unavailable, manual profile editing and deterministic assessment must continue to function.

For explanations, prefer templates populated from the breakdown (e.g., `annual shortfall × years + one-time goals − selected assets − existing coverage`) and use AI only for optional conversational paraphrasing that does not introduce new numbers or claims. Educational term/permanent copy must come from a reviewed content catalog; permanent insurance may include features beyond a death benefit, and whole life is one type of permanent insurance. Never generate brand-specific claims or product recommendations.

## 6. API contract (`/v1`)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/sessions` | Create anonymous or authenticated session; return ID, revision, and bearer token. |
| `GET` | `/v1/sessions/{session_id}` | Get current canonical profile, progress, and last assessment status. |
| `GET` | `/v1/sessions/{session_id}/profile` | Get the current profile directly; useful for the "review your assumptions" step. |
| `DELETE` | `/v1/sessions/{session_id}` | Delete session and all associated data; returns `204`. Required for privacy and demo reset. |
| `POST` | `/v1/sessions/{session_id}/messages` | Submit a user turn; extract facts, update profile, return answer and assessment summary. |
| `PATCH` | `/v1/sessions/{session_id}/profile` | Explicit user correction; triggers recalculation and marks prior assessment stale. |
| `POST` | `/v1/sessions/{session_id}/assessments` | Compute and save an immutable assessment against current profile revision. |
| `GET` | `/v1/sessions/{session_id}/assessments/latest` | Retrieve most recent result with `is_current` and `stale_reason`. |
| `POST` | `/v1/sessions/{session_id}/scenarios` | Calculate a **nonpersistent** what-if override; canonical profile unchanged. |
| `GET` | `/v1/content/coverage-types` | Return approved term/permanent education content. |
| `GET` | `/v1/health` | Liveness only; returns `{"status": "ok"}`. Never leak config, versions, or env. |

**Auth:** Issue a short-lived opaque bearer token (a cryptographically random 32-byte hex string, not a JWT for MVP — no signature verification surface) on session creation. Store a SHA-256 hash of it in the `session_tokens` table. Default expiry: 4 hours; return `expires_at` in the create-session response so the client knows when to prompt for a new session. A session ID alone is **not** authorization.

Token refresh: `POST /v1/sessions/{session_id}/token` with a valid current token returns a new token and updated `expires_at`, invalidating the previous one. This prevents live demo interruptions from expiry.

For local development React (`localhost:5173`) and FastAPI (`localhost:8000`) are cross-origin: set `CORS_ORIGINS=http://localhost:5173` via env var; never commit wildcard origins. In production, lock to the CloudFront or Amplify domain.

**Canonical error envelope** — every non-2xx response uses this shape:

```json
{
  "error": {
    "code": "stale_revision",
    "message": "The session has been updated since your request was formed.",
    "current_revision": 6,
    "request_id": "req_01HXZ..."
  }
}
```

`code` is a stable machine-readable string the frontend switches on. `request_id` mirrors the `X-Request-ID` header for support correlation. Error codes in use:

| Code | Status | Meaning |
|---|---|---|
| `validation_error` | 422 | Malformed or out-of-range input field |
| `unauthorized` | 401 | Missing or invalid bearer token |
| `forbidden` | 403 | Token valid but does not own this session |
| `not_found` | 404 | Session or resource does not exist (do not distinguish "exists but forbidden") |
| `stale_revision` | 409 | `expected_revision` did not match; `current_revision` included |
| `duplicate_request` | 409 | Same `client_request_id` submitted with different payload |
| `turn_limit_exceeded` | 429 | Session has reached the turn ceiling |
| `rate_limited` | 429 | Too many requests from this client |
| `ai_unavailable` | 503 | Model call failed and no fallback could serve the turn |

Create session: `POST /v1/sessions` body `{}` returns `201`:

```json
{
  "session_id": "<opaque-id>",
  "revision": 0,
  "access_token": "<32-byte-hex>",
  "expires_at": "2025-06-15T18:00:00Z"
}
```

Message request:

```json
{
  "text": "We spend about $80,000 a year, and my spouse earns $20,000.",
  "client_request_id": "86ca9e70-dc1c-45dd-83ab-68ceb6e363a8",
  "expected_revision": 3
}
```

Message response:

```json
{
  "session_id": "<opaque-id>",
  "revision": 4,
  "assistant_message": "About how many years would you want that support to continue?",
  "next_question": {
    "field": "support_years",
    "text": "About how many years would you want that support to continue?",
    "input_type": "integer",
    "min": 1,
    "max": 50
  },
  "profile": {"...": "canonical validated fields and provenance"},
  "assessment": {"status": "incomplete", "missing_fields": ["support_years"]},
  "warnings": []
}
```

`next_question` is a structured object so the frontend can render a typed input component rather than parsing free-form text. `input_type` maps to UI controls: `integer`, `currency`, `select`, `boolean`. `assistant_message` is the conversational phrasing for the chat view. When all required fields are collected, `next_question` is `null`.

Profile patch request (typed, not free-form JSON Patch):

```json
{
  "expected_revision": 4,
  "updates": {"support_years": 15},
  "client_request_id": "6fbb3d7c-6288-4ce1-8b27-c540717e3c7c"
}
```

Scenario request: `{ "base_revision": 4, "overrides": { "support_years": 20, "exclude_employer_coverage": true } }`. Response includes `base_revision`, changed assumptions, line items, and resulting gap; the canonical profile is unchanged. Reject unsupported override keys with `validation_error`. For frequent what-if calls (e.g., a slider), debounce on the client side; consider publishing the v1 formula as a mirrored TypeScript utility to avoid a round-trip per drag event.

Assessment response:

```json
{
  "id": "<opaque-id>",
  "status": "complete",
  "profile_revision": 4,
  "is_current": true,
  "stale_reason": null,
  "calculation_version": "needs-v1",
  "currency": "USD",
  "annual_shortfall": 60000,
  "line_items": [
    {"code": "ongoing_support",  "label": "Ongoing support",    "amount": 900000,  "display_order": 1},
    {"code": "one_time_expenses","label": "One-time expenses",  "amount": 50000,   "display_order": 2},
    {"code": "available_assets", "label": "Assets applied",     "amount": -30000,  "display_order": 3},
    {"code": "existing_coverage","label": "Existing coverage",  "amount": -250000, "display_order": 4}
  ],
  "additional_coverage_gap": 670000,
  "assumptions": ["Support for 15 years", "Nominal dollars; no inflation adjustment"],
  "warnings": ["Employer coverage may change with employment."],
  "disclaimer": "Planning estimate, not a quote or a product recommendation."
}
```

When `is_current` is `false`:

```json
{
  "is_current": false,
  "stale_reason": "Profile updated at revision 6; this assessment reflects revision 4."
}
```

## 7. PostgreSQL persistence

Use **PostgreSQL 16** via **SQLAlchemy 2 (async)** with `asyncpg` as the driver. Run migrations with **Alembic**; every schema change is a versioned migration script — never mutate the schema manually in any environment.

### Table design

```sql
-- Sessions: one row per session; profile stored as JSONB
CREATE TABLE sessions (
    id            TEXT        PRIMARY KEY,           -- opaque random ID
    revision      INTEGER     NOT NULL DEFAULT 0,
    turn_count    INTEGER     NOT NULL DEFAULT 0,
    status        TEXT        NOT NULL DEFAULT 'active',
    schema_version TEXT       NOT NULL DEFAULT 'v1',
    profile       JSONB       NOT NULL DEFAULT '{}',
    conversation_state JSONB  NOT NULL DEFAULT '{}',
    expires_at    TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Messages: bounded history per session
CREATE TABLE messages (
    id            TEXT        PRIMARY KEY,
    session_id    TEXT        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role          TEXT        NOT NULL CHECK (role IN ('user', 'assistant')),
    content       TEXT        NOT NULL,
    turn_id       TEXT        NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX messages_session_created ON messages (session_id, created_at DESC);

-- Assessments: immutable snapshots; never updated after insert
CREATE TABLE assessments (
    id                  TEXT        PRIMARY KEY,
    session_id          TEXT        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    profile_revision    INTEGER     NOT NULL,
    profile_snapshot    JSONB       NOT NULL,   -- frozen input at time of calculation
    calculation_version TEXT        NOT NULL,
    result              JSONB       NOT NULL,   -- line items, gap, assumptions, warnings
    status              TEXT        NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX assessments_session_created ON assessments (session_id, created_at DESC);

-- Tokens: hashed bearer tokens linked to sessions
CREATE TABLE session_tokens (
    token_hash    TEXT        PRIMARY KEY,       -- SHA-256 hex of the raw token
    session_id    TEXT        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    expires_at    TIMESTAMPTZ NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX tokens_session ON session_tokens (session_id);

-- Idempotency: deduplication records keyed by client_request_id
CREATE TABLE idempotency_records (
    client_request_id TEXT        PRIMARY KEY,
    session_id        TEXT        NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    response_cache    JSONB,                     -- cached response body for replays
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at        TIMESTAMPTZ NOT NULL
);
```

**Why JSONB for `profile` and `result`:** The profile shape evolves with calculation versions and user-specific optional fields. JSONB lets you query and index specific keys (`profile->>'support_years'`) while keeping schema migrations lightweight. Assessments are immutable snapshots — JSONB avoids needing versioned result columns. All other columns with fixed semantics are typed SQL columns.

### Concurrency and optimistic locking

Use PostgreSQL's optimistic locking on the `revision` column instead of DynamoDB conditional writes:

```python
# In postgres.py
result = await db.execute(
    update(Session)
    .where(Session.id == session_id, Session.revision == expected_revision)
    .values(profile=new_profile, revision=Session.revision + 1, updated_at=func.now())
    .returning(Session.revision)
)
if result.rowcount == 0:
    current = await db.scalar(select(Session.revision).where(Session.id == session_id))
    raise StaleRevisionError(current_revision=current)
```

On conflict, return `409` with `current_revision` so the client can reload and retry. Because a message turn involves an external Bedrock call, wrap only the *database writes* (profile update, message insert, idempotency record) in a single `BEGIN / COMMIT` transaction *after* the model call completes. Never write model-extracted facts against a stale revision.

### Session expiry

PostgreSQL has no built-in TTL. Enforce expiry in two ways:
1. **Application-level:** check `expires_at > now()` on every session load; return `401` if expired.
2. **Cleanup job:** a periodic task (pg_cron or a scheduled Lambda/ECS task) deletes rows where `expires_at < now() - INTERVAL '1 hour'`, giving a grace window for in-flight requests.

Retain only the last 10 messages per session for the AI context window. The cleanup job or a post-session trigger can prune older rows from the `messages` table.

### Local development

The `docker-compose.yml` runs a `postgres:16-alpine` container on port `5432`. No credentials are needed beyond the local compose password. Apply migrations with `alembic upgrade head` against `DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/insurance`.

```yaml
# docker-compose.yml (database service)
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: insurance
      POSTGRES_USER: insurance
      POSTGRES_PASSWORD: localdev
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
```

### AWS hosting

Use **Amazon RDS for PostgreSQL** (or Aurora PostgreSQL Serverless v2 for auto-scaling). Place the RDS instance in a private subnet; the FastAPI container (ECS Fargate or App Runner with VPC connector) accesses it over a VPC private endpoint — never over the public internet. Store the database password in **AWS Secrets Manager**; inject it at container startup via the ECS secrets injection mechanism or App Runner's secrets support. Do not pass the password as a plaintext environment variable.

Use separate databases per environment: `insurance_dev`, `insurance_demo`, `insurance_prod`. Scope the IAM task role to allow `secretsmanager:GetSecretValue` on the specific secret ARN only; the database itself uses password auth (not IAM auth) for PostgreSQL compatibility.

Enable RDS encryption at rest (AWS-managed key) and enforce SSL connections (`rds.force_ssl=1`). Enable automated backups with a retention period appropriate for the environment (1 day for dev/demo, 7+ days for prod).

## 8. Secrets and configuration

Never hardcode secrets or commit them to source control. All runtime config is read from environment variables via `pydantic-settings` in `settings.py`.

| Variable | Description |
|---|---|
| `ENV` | `local` \| `dev` \| `demo` \| `prod` |
| `DATABASE_URL` | Full async DSN: `postgresql+asyncpg://user:pass@host:5432/dbname`. **For local only** — in AWS, construct from Secrets Manager at startup. |
| `DB_POOL_SIZE` | SQLAlchemy async pool size, default `10` |
| `DB_MAX_OVERFLOW` | Max connections above pool size, default `5` |
| `BEDROCK_MODEL_ID` | Approved Bedrock model ARN |
| `BEDROCK_GUARDRAIL_ID` | Guardrail resource ID (required in non-local envs) |
| `CORS_ORIGINS` | Comma-separated allowed origins; never `*` with credentials |
| `SESSION_TTL_HOURS` | Session expiry, default `4` |
| `SESSION_TURN_LIMIT` | Max turns per session, default `40` |
| `MESSAGE_MAX_CHARS` | Max user message length, default `2000` |
| `LOG_LEVEL` | `INFO` in prod; `DEBUG` locally |
| `BEDROCK_TIMEOUT_SECONDS` | Hard timeout for model calls, default `15` |

**Database credentials in AWS:** store the RDS password in **AWS Secrets Manager**. At container startup, `settings.py` fetches the secret and constructs `DATABASE_URL` — it is never stored as a plaintext environment variable in the task definition. The IAM task role must have `secretsmanager:GetSecretValue` on the specific secret ARN. Bedrock access uses the same IAM task role — no separate API keys are needed.

The `settings.py` module must validate on startup and raise a clear error if required variables are missing or the database connection cannot be established, preventing a misconfigured container from silently serving bad data.

## 9. Security, privacy, and compliance boundaries

- Session IDs and bearer tokens must be cryptographically random (`secrets.token_hex(32)`). Rate-limit: max 10 new sessions per IP per hour, max 60 message turns per IP per minute, enforced via a lightweight in-process counter (or an ALB WAF rule in production).
- Configure explicit CORS origins (see §8); no wildcard with credentials. Require HTTPS everywhere; the ALB or App Runner listener handles TLS termination. Enforce a 16 KB request body limit in the FastAPI middleware.
- Treat all user messages, model outputs, retrieved resources, and citations as untrusted. A user message containing "ignore previous instructions" must not change calculator rules or system policies — enforce this in code, not only in the system prompt.
- Enable Bedrock Guardrails with a content filter appropriate for financial guidance: block harmful content, deny PII extraction requests, and block URLs generated by the model from being treated as authoritative resources.
- Redact sensitive fields from all logs. Structured log fields: `request_id`, `session_id` (hashed or truncated), `turn_number`, `endpoint`, `duration_ms`, `status_code`, `calculation_version`, `ai_model_id`, `ai_latency_ms`, `error_code`. Never log `text`, `profile` values, or assessment amounts in production logs.
- Do not collect social security numbers, addresses, full account numbers, medical data, beneficiary names, or birthdates. Clarify in the UI that all amounts are estimates entered by the user.
- Show model-independent limitations on every assessment: inflation and investment returns are not modeled; employer coverage portability is not guaranteed; product features and availability vary by jurisdiction.
- Add audit trails and formal compliance review before any real customer-facing launch beyond the hackathon.

## 10. Tests and acceptance criteria

**Tooling:** `pytest` with `pytest-asyncio` for async routes. Maintain ≥ 80 % line coverage on `calculators/`, `services/`, and `security/`. Run `mypy --strict` on `domain/`, `calculators/`, and `contracts/` to catch type errors before runtime. Run `ruff` for linting. All of these run in CI on every pull request (see §12).

**Unit tests:** calculator pure-function fixtures; integer arithmetic and rounding; `null` vs zero for unknown fields; negative raw gap (zero additional gap); source/provenance metadata; mutually exclusive mortgage handling; scenario overrides do not mutate canonical profile; employer coverage included vs excluded; policy-version pinning; income estimation sub-flow produces `source: "assumption", confirmed: false`; token hashing and expiry.

**Service tests:** extraction maps natural language to typed profile fields; explicit user correction overrides prior extracted value; contradictory answer triggers clarification rather than overwrite; model JSON with unknown keys is rejected by Pydantic; malicious instruction in model output does not alter calculator behavior; AI timeout falls back to manual flow without error; no AI-extracted amount appears in the official assessment result.

**API tests (httpx + pytest):** bearer token required on all session endpoints; token from session A rejected on session B; stale `expected_revision` returns `409` with `current_revision`; duplicate `client_request_id` with same payload is idempotent (same response); duplicate with different payload returns `409 duplicate_request`; profile patch triggers assessment recalculation and marks prior assessment `is_current: false` with populated `stale_reason`; turn limit returns `429 turn_limit_exceeded`; `DELETE` session removes all items; invalid monetary amounts (decimals, negatives) return `422 validation_error`; CORS rejects unlisted origins; oversized request body returns `413`.

**Integration tests:** full session flow against a PostgreSQL test database (spun up via `docker-compose` in CI); Bedrock adapter replaced with stub; limited live smoke test against the dev environment database. Apply Alembic migrations as part of the integration test setup. Fixture files record: input profile → calculation version → expected exact line items; any change to calculator output must be intentional and update the fixture.

**Demo acceptance:** Start a fresh anonymous session; answer all seven question-flow steps; inspect and edit the profile directly via PATCH; produce a complete assessment with correct line-item math; change personal coverage from $100k to $300k and confirm the gap falls by exactly $200k; run a scenario comparison for 10 vs 20 year horizons; read a term/permanent explanation from the content catalog; delete the session and confirm all data is gone; verify the whole flow works without the AI (stub mode).

## 11. Deployment and infrastructure

### Container

The `Dockerfile` uses a multi-stage build: a `builder` stage installs dependencies into a virtual environment, and a minimal `python:3.12-slim` runtime stage copies only the venv. Pin the base image digest. Set `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`, and run as a non-root user.

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt --target /build/venv

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /build/venv /app/venv
COPY app/ ./app/
ENV PYTHONPATH=/app/venv
RUN adduser --disabled-password appuser && chown -R appuser /app
USER appuser
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### Hosting options (pick one for demo)

| Option | Pros | Cons |
|---|---|---|
| **AWS App Runner** | Zero infra config, built-in TLS, auto-scales, deploys from ECR | Less control over networking |
| **ECS Fargate + ALB** | Full control, WAF, production-grade | More setup time |

App Runner is recommended for the hackathon: push to ECR, point App Runner at the image, set env vars in the service config, done. For production, migrate to ECS Fargate behind an ALB with a WAF rule set.

### React hosting

Host the built React app on **S3 + CloudFront** or **AWS Amplify Hosting**. Amplify is faster to set up for a hackathon (connect the repo, set the build command, deploy). Set the CloudFront or Amplify domain as the only allowed CORS origin in the backend.

### Environment promotion

```text
local  ->  dev (auto-deploy on merge to main)  ->  demo (manual promote + smoke test)
```

Never deploy directly to demo without a passing smoke test in dev. Keep demo environment config separate from dev to avoid accidental data mixing.

### Pre-demo go-live checklist

- [ ] Container image built from pinned base, pushed to ECR, deployed to App Runner (or ECS Fargate)
- [ ] RDS PostgreSQL `insurance_demo` database created in a private subnet; SSL enforced
- [ ] Alembic migrations run against the demo database (`alembic upgrade head`)
- [ ] Database password stored in AWS Secrets Manager; IAM task role has `GetSecretValue` on that ARN
- [ ] App Runner VPC connector (or ECS security group) allows outbound to RDS on port 5432 only
- [ ] All required env vars set in App Runner / ECS task definition (verify with startup health check)
- [ ] HTTPS confirmed on App Runner URL; React app served over HTTPS
- [ ] CORS locked to the React app's production domain; wildcard removed
- [ ] IAM task role attached with least-privilege Bedrock and Secrets Manager permissions
- [ ] Bedrock Guardrails enabled on the demo service
- [ ] Smoke test script passes end-to-end (create session → full conversation → assessment → delete)
- [ ] AWS Budgets alert set to notify if daily Bedrock spend exceeds threshold
- [ ] CloudWatch alarm on 5xx error rate > 1 % for the App Runner / ECS service
- [ ] RDS Enhanced Monitoring enabled; set alarm on DB connections approaching max
- [ ] `GET /v1/health` returns `200` from the public URL (health check should verify DB connectivity)

## 12. CI pipeline

`.github/workflows/ci.yml` runs on every pull request and on merge to `main`:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    env:
      POSTGRES_DB: insurance_test
      POSTGRES_USER: insurance
      POSTGRES_PASSWORD: testpass
    ports:
      - "5432:5432"
    options: >-
      --health-cmd pg_isready
      --health-interval 5s
      --health-retries 5

steps:
  - name: Lint
    run: ruff check app/

  - name: Type check
    run: mypy app/domain app/calculators app/contracts --strict

  - name: Run migrations
    run: alembic upgrade head
    env:
      DATABASE_URL: postgresql+asyncpg://insurance:testpass@localhost:5432/insurance_test

  - name: Unit + API tests
    run: pytest tests/unit tests/api --cov=app --cov-fail-under=80
    env:
      DATABASE_URL: postgresql+asyncpg://insurance:testpass@localhost:5432/insurance_test

  - name: Integration tests
    run: pytest tests/integration
    env:
      DATABASE_URL: postgresql+asyncpg://insurance:testpass@localhost:5432/insurance_test

  - name: Build container image
    run: docker build -t insurance-backend:${{ github.sha }} .
```

The CI job uses a GitHub Actions service container for PostgreSQL — no Docker-in-Docker needed. Alembic migrations run before any tests so the schema is always up to date in CI. The Bedrock adapter is replaced by the stub for all CI runs. A live Bedrock smoke test runs only in the dev environment post-deploy, not in CI.

## 13. Incremental implementation plan

1. **Contract first:** Agree with frontend on profile schema, required fields, sample API responses, error envelope shape, `next_question` input types, and auth mechanism (bearer token). Freeze `/v1` contracts. Share the OpenAPI spec (auto-generated by FastAPI at `/docs`) and fixture payloads before any frontend work begins.
2. **Pure calculator:** Implement `needs-v1` as a pure function with full test coverage. Add missing-field detection, provenance metadata, and no-double-count validation. This is the most important piece — get it right first.
3. **In-memory session API:** Implement the `SessionRepository` interface and in-memory version. Wire up all endpoints. The entire product must work without a database, LLM, or AWS at this point. Share the running local server with the frontend team.
4. **PostgreSQL persistence:** Write the SQLAlchemy ORM models and the Alembic initial migration. Implement `repositories/postgres.py` and swap it in behind the repository interface. Run integration tests against the local Docker PostgreSQL. Add optimistic locking, expiry enforcement, and idempotency records. Token storage and verification.
5. **Conversational workflow:** Add Bedrock behind the `AIAdapter` interface with strict Pydantic validation on all outputs and a deterministic fallback path. Include the income estimation sub-flow. Enable Guardrails.
6. **Educational content and explanations:** Add approved term/permanent copy to the content catalog, scenario-specific observation templates, and verified resource links.
7. **Deploy to dev:** Provision RDS PostgreSQL dev instance in a private subnet. Run `alembic upgrade head`. Build container, push to ECR, deploy to App Runner dev service with VPC connector. Run smoke tests. Lock CORS to the deployed React URL.
8. **Hardening and pre-demo:** Work through the pre-demo go-live checklist in §11. Set cost and DB connection alarms. Promote to demo environment.

## 14. Extension points for continued development

- **Calculator policies:** Implement `CalculationPolicy` per version; do not silently change old result meaning. Future versions may include yearly cash-flow schedules, inflation/discount rates, retirement dates, or tax assumptions.
- **Provider abstraction:** `AIAdapter.extract_candidates(...)` and `AIAdapter.phrase_question(...)`; swap Bedrock models or add a secondary provider without changing domain logic.
- **Persistence abstraction:** `SessionRepository`; the interface is already implemented against PostgreSQL. Swap to a different relational engine or add read replicas without changing domain logic.
- **Questions as configuration:** Question definitions include required field, prerequisites, approved phrasing, and validation; add new topics without rewriting routing logic.
- **Content catalog:** Versioned reviewed product education and resource URLs; allow updates independently of the calculator.
- **Identity and reporting:** Add signed-in accounts and analytics only when needed, with explicit consent, retention rules, and clear separation between anonymous planning sessions and customer records.
- **Frontend scenario mirroring:** Publish the v1 formula as a TypeScript package so the React app can run instant what-if calculations client-side, using the server result only to seed the initial state.
- **Authenticated users:** Replace anonymous sessions with signed-in identities (Cognito or an OIDC provider) when multi-session history or account management is needed.

**Recommended first deliverable:** a profile PATCH API plus the deterministic calculator returning reproducible line items. Once the React app can complete the full experience manually, add Bedrock as an enhancement rather than making the model a dependency for the basic product.