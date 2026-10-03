# Frontend file guide

What each file added for the front end does, and how it fits into the app.
Paths are relative to the repository root. Generated folders (`node_modules/`, `dist/`) are not
listed; they are ignored by git.

## How the pieces connect

```text
main.tsx → App.tsx (routes)
             └─ SessionProvider (session/SessionContext.tsx)  ← holds all app state
                  └─ Layout (header, nav, error banner, footer)
                       ├─ HomePage
                       ├─ PlannerPage → ChatPanel → QuestionInput → ExpenseEditor
                       │              → AssessmentPanel
                       ├─ ProfilePage → ExpenseEditor
                       └─ LearnPage
Components call useSession() (session/context.ts) → api/client.ts → FastAPI backend /v1
```

## Application code (`frontend/src/`)

| File | What it does |
|---|---|
| `src/main.tsx` | Entry point. Mounts the React app into the `#root` element of `index.html` and loads the global stylesheet. |
| `src/App.tsx` | Top-level component. Wraps the app in the session provider and sets up the routes: `/` (Home), `/planner`, `/profile` (My answers), `/learn`, and a not-found page. |
| `src/index.css` | All styling for the app: colors (light and dark mode), buttons, layout, chat bubbles, the estimate table and the profile rows. |

### `src/api/` — talking to the backend

| File | What it does |
|---|---|
| `src/api/types.ts` | TypeScript copies of the backend's data shapes: the profile (dependents, income, debts, coverage), questions, the estimate and its line items, chat messages, requests and errors. Must be kept in sync with `backend/app/contracts/`. |
| `src/api/client.ts` | The only place that makes HTTP calls. Adds the login token to each request, turns backend errors into an `ApiError` with a readable message and code, creates unique request IDs, and has one function per backend endpoint (create session, edit profile, send message, save estimate, and so on). |

### `src/session/` — app state

| File | What it does |
|---|---|
| `src/session/SessionContext.tsx` | The app's "brain". On load it restores the user's session (or creates a new one), and it holds the profile, estimate, chat history and errors. It provides the actions the UI uses: send a chat message, edit or confirm answers, save the estimate, and start over. It also recovers from conflicts (reloads if answers changed elsewhere) and from expired sessions (starts a new one). |
| `src/session/context.ts` | Defines the shape of the shared state and the `useSession()` hook that any component calls to read state or trigger actions. Kept separate from the provider so React's hot reload works during development. |

### `src/components/` — reusable building blocks

| File | What it does |
|---|---|
| `src/components/Layout.tsx` | The page frame shown on every screen: app name, navigation links, the "Start over" button (deletes the session), an error banner, and the "planning estimate only" footer. |
| `src/components/ChatPanel.tsx` | The conversation view. Shows the chat history, the backend's current question, and a text box to answer in your own words. Warns when the session's message limit is close. |
| `src/components/QuestionInput.tsx` | The form control under each question, chosen by the question type: a number box, a dollar box, the expenses form, or a review list with "These look right". Offers "I don't know" where allowed. Answers are saved directly to the profile. |
| `src/components/ExpenseEditor.tsx` | A form for one-time costs (final expenses, education, debt payoff, mortgage payoff, other), one amount per category, with a running total. Used in the chat and on the My answers page. |
| `src/components/AssessmentPanel.tsx` | The estimate display. Shows the status (not enough info / preliminary / complete), the coverage gap, every calculation row in full dollars, assumptions, warnings, limitations, the disclaimer, and the "Save this estimate" button. |

### `src/pages/` — full screens

| File | What it does |
|---|---|
| `src/pages/HomePage.tsx` | Landing page explaining what the tool does, with "Get started" and "Learn" buttons. |
| `src/pages/PlannerPage.tsx` | The main screen: the chat on one side and the live estimate on the other. Shows a loading or connection-error message if the backend isn't reachable. |
| `src/pages/ProfilePage.tsx` | "My answers". Lists every answer by topic (dependents, income and support, debts, coverage and assets, preferences), shows whether each is confirmed or came from chat, and lets the user edit, mark as "don't know", or confirm all. |
| `src/pages/LearnPage.tsx` | Educational page about term vs. permanent life insurance. The text comes from the backend's content endpoint. |
| `src/pages/NotFoundPage.tsx` | Shown for any URL that doesn't match a route. |

### `src/utils/`

| File | What it does |
|---|---|
| `src/utils/format.ts` | Display helpers. Formats money in full dollars (`$1,250,000`, never `$1.3M`), maps field names to readable labels, shows "Not answered yet" / "Don't know" correctly, and parses typed amounts like `$80,000` into whole numbers. |

## Project configuration (`frontend/`)

| File | What it does |
|---|---|
| `index.html` | The single HTML page the app loads into. Sets the browser tab title and icon. |
| `package.json` | Lists the libraries the front end uses (React, React Router, Vite, TypeScript, oxlint) and the commands: `npm run dev`, `build`, `lint`, `typecheck`, `preview`. |
| `package-lock.json` | Pins the exact library versions so every teammate and CI installs the same thing. Generated by npm; don't edit by hand. |
| `vite.config.ts` | Dev server and build settings. Forwards `/v1` API calls to the backend (port 8000 by default, or `API_PROXY_TARGET`) so local development needs no CORS setup. |
| `tsconfig.json` | Root TypeScript config that points to the two configs below. |
| `tsconfig.app.json` | TypeScript rules for the app code in `src/` (strict checks, React JSX). |
| `tsconfig.node.json` | TypeScript rules for build tooling files such as `vite.config.ts`. |
| `.oxlintrc.json` | Linter rules (catches React hook mistakes and similar bugs). |
| `.env.example` | Template for environment settings: `VITE_API_BASE_URL` (backend address for deployed builds) and `API_PROXY_TARGET` (dev proxy). Copy to `.env.local` to use. Never put secrets here. |
| `.gitignore` | Keeps `node_modules/`, `dist/`, logs and local env files out of git. |
| `public/favicon.svg` | Browser tab icon (Vite default; replace with a project logo). |
| `public/icons.svg` | Leftover from the Vite template and not used by the app; safe to delete. |
| `README.md` | How to run, check and understand the front end, plus what isn't built yet. |
| `FILE_GUIDE.md` | This file. |

## Changes outside `frontend/`

| File | What it does |
|---|---|
| `.github/workflows/frontend-ci.yml` | GitHub Actions job that runs on pull requests and pushes to `main` touching `frontend/`: installs dependencies, lints, type-checks and builds. A PR fails if any step fails. |
| `README.md` (root, edited) | The `frontend/` row now links to the frontend README instead of saying "not started yet". |
