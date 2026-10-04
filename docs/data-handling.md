# What Coverage Compass keeps, where, and for how long

The answers this tool collects are somebody's income, their debts and their children's ages. We
decided to keep each answer only where computing or showing the cover amount needs it, never in a
log, and for a stated time. This page records those decisions; the code links show where each one
is enforced.

## What we ask, and why

Only what the cover calculation or the coverage-type explanation reads. We used to ask the
person's own age; nothing used it, so we stopped asking
([profile.ts](../frontend/src/domain/profile.ts)).

| Answer | Used for |
|---|---|
| Who depends on them, number of children, youngest's age | Years of income support and college (`compute()` in [needs.ts](../frontend/src/domain/needs.ts)) |
| Yearly income, years of support | Income replacement |
| Mortgage balance and years left, other debts | Debts to clear; the matching term |
| College plan | College line |
| Coverage through work, policies they own, savings to count | Coverage already in place |
| Comfortable monthly budget | The budget figures and the "Fitting your budget" trade-off |
| Five coverage-type preferences | Term or permanent ([policy.ts](../frontend/src/domain/policy.ts)) |

We never ask for Social Security, account or card numbers, and the callback form rejects anything
that looks like one ([contracts/support.py](../backend/app/contracts/support.py)).

## Where each piece goes

| Where | What | How long |
|---|---|---|
| **The browser** | The sign-in token, its expiry, and the name and email to show (`cc-auth`); display settings (`cc-preferences`). Never the answers: those stay in memory while the page is open. | Until sign-out, or the token expires (7 days). |
| **Our database** (PostgreSQL on Amazon RDS: encrypted at rest, TLS required) | Accounts: email, first name, and an Argon2id password hash (never the password). Saved answers, change log and checklist, so the person can pick up on any device. | Until the person deletes their account (My info → Delete my account), or **180 days after their last sign-in**, when it is deleted automatically. |
| | Sign-in tokens and password reset links, stored only as SHA-256 hashes. | Until they expire (7 days, 30 minutes), then deleted. |
| | Callback requests ("Talk to a licensed representative"): name, the one contact method chosen, what they want help with, and the estimate summary only if they tick the box. | **30 days**, so a representative can follow up; deleted sooner if the account is deleted. |
| **Database backups** (RDS automated backups) | A copy of the above. | 7 days, so a deletion is complete after at most a week. |
| **The AI model** (Claude, through the Anthropic API, only when switched on) | Onboarding: the one answer being read, plus the current answers (needed for replies like "2x salary"). Chat: the answers and the last few chat turns, so it can explain the estimate. Never the name, email or password. | Not stored by us. The provider's API data terms apply. |
| **Logs** (CloudWatch) | Only allow-listed fields: request ID, route, status, timing, model name, a short hashed account reference ([logging_config.py](../backend/app/logging_config.py)). No answers, emails or contact details. Crash logs keep the stack trace but not the error message, which could quote a value. | 30 days. |

Without the AI model, nothing leaves our servers: onboarding uses the built-in parser and Chat uses
standard answers.

## How deletion works

- **On request:** `DELETE /v1/account` (My info → Delete my account) deletes the account and,
  through the database's cascading deletes, its tokens, reset links and saved answers, plus any
  callback requests sent while signed in
  ([personal_data.py](../backend/app/services/personal_data.py)). Accounts with a password must
  enter it first.
- **On schedule:** every running server sweeps at start-up and every 6 hours, deleting accounts
  unused for 180 days, callback requests older than 30 days, and expired tokens and links.
  The periods are settings (`ACCOUNT_RETENTION_DAYS`, `CALLBACK_RETENTION_DAYS`,
  `RETENTION_SWEEP_HOURS`) in [settings.py](../backend/app/settings.py).
- **Earlier browser-only data:** the version before accounts kept answers in `localStorage`. The
  first time that person signs in, their profile moves into their account and every old key is
  removed ([profileStore.ts](../frontend/src/services/profileStore.ts)).

## What the model may say about money

The model explains the estimate; it never produces it. Every dollar figure in its answer is checked
against the amounts the code computed for this person (or ones they typed themselves) before it is
shown; an answer with any other figure is replaced by a standard answer that says why
([figures.py](../backend/app/domain/figures.py)).
