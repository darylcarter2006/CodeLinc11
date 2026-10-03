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
- Interactive docs (OpenAPI): http://localhost:8000/docs

You don't need a database or AWS credentials. Sessions are kept in memory, and a rule-based stub
stands in for the AI model.

## Checks (the same ones CI runs)

```bash
.venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests
.venv/bin/mypy app tests                       # strict mode
.venv/bin/pytest --cov=app --cov-fail-under=90
docker build -t insurance-backend .
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
  repositories/      SessionRepository interface + in-memory implementation
  ai/                AIAdapter interface + deterministic stub
  content/           reviewed educational copy (pending compliance review)
  security/          token generation/hashing, log redaction
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

- **Postgres** (step 4): implement `SessionRepository` in `repositories/postgres.py`, select it
  in `container.build_repository`, and add Alembic. For the multi-instance version of
  `session_lock`, insert a *pending* idempotency record before the model call.
- **Bedrock** (step 5): implement `AIAdapter` in `ai/bedrock.py` and select it in
  `container.build_ai_adapter`. Validation of model output already lives in
  `services/extraction.py`.
- **Income-estimation sub-flow:** needs `annual_income` and expense-share fields.
- **Assumption-flag questions:** the mortgage/education double-count flags can be set by
  PATCH, and the calculator warns about them, but the chat doesn't ask yet.
- **Rate limiting:** do this at the edge (WAF/App Runner) rather than in-process.
- **Verified resource links:** `content/catalog.py` has `RESOURCES` empty on purpose.
