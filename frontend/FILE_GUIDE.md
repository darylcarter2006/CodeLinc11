# Frontend file guide

What each front-end file does, and how it fits into Coverage Compass.
Paths are relative to `frontend/`. Generated folders (`node_modules/`, `dist/`) are not listed.

## How the pieces connect

```text
main.tsx → BrowserRouter → AppProvider (state/AppContext.tsx) → App.tsx (routes)
  Layout (navy top bar, tabs, account button, footer)
    /auth        AuthPage
    /onboarding  OnboardingPage ── domain/parse.ts + services/ai.ts (extract)
    /dashboard   DashboardPage  ┐
    /breakdown   BreakdownPage  ├─ domain/needs.ts (compute, tradeoffs, next steps)
    /info        MyInfoPage     │
    /chat        ChatPage       ┘─ services/ai.ts (chat) or services/fallback.ts
  RouteGuard sends each user to the right area: not signed in → auth, not confirmed → onboarding.
State is saved through services/auth.ts and services/profileStore.ts (browser storage for now).
```

## Logic (`src/domain/`)

| File | What it does |
|---|---|
| `domain/profile.ts` | The `Profile` and `SavedProfile` types, the Maya example, field labels, display helpers, and the onboarding question order with each question's condition and quick replies. |
| `domain/needs.ts` | The needs calculation, ported exactly from the prototype: income replacement, debts, college, final expenses, the gap, the rounded starting point, range and term. Also builds the personalized tradeoff cards and next-steps checklist. |
| `domain/parse.ts` | The local answer parser (understands "85k", "2x salary", "until my youngest is 22", and so on), `clean()` to keep only valid values from the AI or the parser, and `applyUpdates()` to merge answers with the derived rules. |
| `domain/glossary.ts` | Plain-language definitions of insurance terms (term life, whole life, cash value, laddering, group life and more) and `findTerms()`, which finds them in a sentence. |
| `domain/explain.ts` | One-sentence explanations of the key numbers (coverage in place, estimated need, left to cover, term, range) built from the person's own values. |
| `domain/format.ts` | Money formatting: full dollars (`$1,408,500`), compact (`$1.41M`), and short dates. |
| `domain/glossary.test.ts`, `domain/explain.test.ts` | Unit tests for finding terms in text and for each number explanation (checked against Maya's example). |
| `domain/needs.test.ts` | Unit tests: the three handoff test vectors, rounding and term edges, tradeoffs and next steps. |
| `domain/parse.test.ts` | Unit tests: a table of phrases → parsed values, `clean()` rejecting bad input, and the merge rules. |

## Services (`src/services/`)

| File | What it does |
|---|---|
| `services/auth.ts` | The `AuthService` interface and a local implementation (one account per browser, name and email only, passwords never stored). Handles email sign-up/log-in and Google sign-in. A real provider can replace it. |
| `services/google.ts` | Google sign-in support: loads Google's sign-in script and reads name and email from the Google token after checking it was issued for this app, hasn't expired and has a verified email. |
| `services/google.test.ts` | Unit tests for reading Google tokens, including tokens for another app, expired tokens and unverified emails. |
| `services/profileStore.ts` | The `ProfileStore` interface for the profile, change log and checked next steps, with a browser-storage implementation. Can move to the backend later. |
| `services/ai.ts` | Calls the backend's `/v1/ai/extract` and `/v1/ai/chat` (streamed). If the backend says AI is unavailable, it switches the app to the local parser and standard answers. |
| `services/fallback.ts` | Standard, keyword-matched answers for the Chat tab when live AI isn't available. |
| `services/support.ts` | The `SupportService` interface for "Talk to a licensed Lincoln Financial representative" callback requests, sending them to the backend and reporting whether they were received, rejected, or can't be sent yet. |
| `services/support.test.ts` | Unit tests for how each backend response (sent, not connected, invalid, failed) is reported. |
| `services/storage.ts` | Safe read/write of `cc-*` keys in `localStorage` (works even if storage is blocked). |
| `services/http.ts` | Small helper for JSON POSTs to the backend, with readable errors. Treats an HTML reply (a static host's page fallback) as "not found". |
| `services/http.test.ts` | Unit tests for the helper: API replies, the HTML fallback, error messages and an unreachable server. |

## State (`src/state/`)

| File | What it does |
|---|---|
| `state/AppContext.tsx` | The app's state: signed-in account, example mode, saved profile, change log, next-step checks, and the Chat conversation. Provides the actions: sign up, log in, sign out / exit example, save onboarding answers, confirm, save My info, and ask a chat question. |
| `state/context.ts` | The shape of that state, the `useApp()` hook, and `areaFor()`, which decides whether a user belongs in auth, onboarding or the app. |

## Components (`src/components/`)

| File | What it does |
|---|---|
| `components/Layout.tsx` | Navy top bar with the wordmark, tabs (only inside the app), and the account button ("Sign out" or "Exit example"). Also the footer note. |
| `components/RouteGuard.tsx` | Redirects users to the area they belong in, and sends `/` to the right start page. |
| `components/ChatLog.tsx` | Chat building blocks shared by onboarding and Chat: the message list (announced to screen readers), quick-reply chips, and the input form. |
| `components/StackedBar.tsx` | Horizontal stacked bars with hover tooltips, plus the direct-labeled legend. |
| `components/Tip.tsx` | Hover/focus/tap explanations: `Term` (an insurance term with its definition), `WithTerms` (adds terms to a sentence) and `NumberInfo` (an "i" button that explains a number). Kept on screen on phones; Escape closes. |
| `components/TradeoffCard.tsx` | Tradeoff cards, optionally with the Term/Whole comparison. |
| `components/CallbackDialog.tsx` | The "Talk to a licensed Lincoln Financial representative" form: name, email or phone, best time, what they need help with, and an opt-in summary of their estimate and recent questions. Validates inline and says plainly when requests can't be sent yet. |
| `components/GoogleButton.tsx` | The "Sign up / Sign in with Google" button. Shows Google's official button when a client ID is set, otherwise a look-alike that explains Google sign-in isn't set up yet. |

## Screens (`src/pages/`)

| File | What it does |
|---|---|
| `pages/AuthPage.tsx` | Sign up / log in with inline errors, the Google button, and "Explore with example data instead". |
| `pages/OnboardingPage.tsx` | The conversational intake: one question at a time, AI extraction with the local parser as backstop, a "Saved so far" panel with progress, and the final confirm step. |
| `pages/DashboardPage.tsx` | Four tiles, coverage today (meter + sources), what the need is made of, two tradeoffs, next steps checklist, and your situation. |
| `pages/BreakdownPage.tsx` | The starting-point headline, both bars, the line-by-line table with "Why?" buttons (open Chat), assumptions, and all tradeoffs. |
| `pages/MyInfoPage.tsx` | Edit every saved answer, with validation, a sticky save bar, and the recent-changes log. |
| `pages/ChatPage.tsx` | Free-form Q&A grounded in the user's numbers, with a "What I know" summary, suggested questions, and a "Talk to a licensed Lincoln Financial representative" link. |

## App entry and styling

| File | What it does |
|---|---|
| `src/main.tsx` | Mounts the app with the router and state provider. |
| `src/App.tsx` | The route table. |
| `src/index.css` | All styles, built from `design-tokens.json`. Light theme only; motion only when the user hasn't asked to reduce it. |
| `index.html` | Page title, browser-tab icons, and the Newsreader / Public Sans fonts. |
| `public/favicon.ico`, `public/icon-192.png`, `public/apple-touch-icon.png` | Browser-tab and home-screen icons made from the Lincoln Financial portrait mark (used with the organizers' permission). |

## Tests and configuration

| File | What it does |
|---|---|
| `src/test/explanations.test.tsx` | Explanations in the app: a dashboard number on keyboard focus (and Escape), a term on hover and tap, and the Breakdown starting point and range. |
| `src/test/flow.test.tsx` | End-to-end: sign up → answer every onboarding question with the local parser → confirm → dashboard tiles match `compute()` → edit income → tiles update and a log entry appears. Also example mode → "Why?" → standard answer, and an inline sign-up error. |
| `src/test/google.test.tsx` | Google sign-in flows: not set up, a new Google user, a returning user who keeps their answers, and a rejected token. |
| `src/test/breakdown.test.tsx` | The Breakdown page when existing coverage already covers the need: it says so and shows no starting-point figure. |
| `src/test/callback.test.tsx` | "Talk to a licensed Lincoln Financial representative" flows: inline validation, sending with and without the shared summary, the not-connected message, closing with Escape, and keeping keyboard focus inside the form. |
| `src/test/setup.ts` | Test setup: DOM matchers and a clean page/storage between tests. |
| `vite.config.ts` | Dev server proxy to the backend and the Vitest settings. |
| `package.json` | Libraries and commands: `dev`, `build`, `lint`, `typecheck`, `test`, `preview`. |
| `package-lock.json` | Exact library versions, generated by npm. |
| `tsconfig*.json`, `.oxlintrc.json` | TypeScript and lint settings. |
| `amplify-rewrites.json` | The rewrite rule to paste into AWS Amplify (Rewrites and redirects) so app pages like `/dashboard` load on refresh, while `/v1/...` API paths are left alone. |
| `.env.example` | Settings template: `VITE_API_BASE_URL` (backend address for builds), `API_PROXY_TARGET` (dev proxy) and `VITE_GOOGLE_CLIENT_ID` (Google sign-in). |
| `README.md` | How to run and test, the ground rules, and the backend AI contract. |

## Elsewhere in the repo

| File | What it does |
|---|---|
| `../docs/coverage-compass/` | The handoff spec, prototype and design tokens this front end implements. |
| `../amplify.yml` | AWS Amplify Hosting build settings for the front end: Node 22, install, build, and publish `frontend/dist`. |
| `../.github/workflows/frontend-ci.yml` | CI on pull requests: lint, tests, type check and build. |
