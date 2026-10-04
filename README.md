# Coverage Compass

A life insurance needs analyzer for codeLinc 11 (Path 2). A short conversation gathers a person's
situation, then shows how much cover might fit, with every line of the arithmetic, the trade-offs
that follow from their answers, and whether term or permanent coverage suits their preferences.
It's an educational estimate, not financial advice or a quote.

## Run it

**Everything in one container** (no network, credentials or database needed). Requires Docker.

```bash
git clone https://github.com/darylcarter2006/CodeLinc11.git
cd CodeLinc11
docker build -t coverage-compass .
docker run --rm -p 8000:8000 coverage-compass
```

Open **http://localhost:8000**. Create an account, or click **"Explore with example data
instead"**. In this mode accounts and saved answers are kept in memory, onboarding uses the
built-in answer parser, Chat gives standard answers, and password reset emails are printed to the
container's log. The [Dockerfile](Dockerfile) is at the repository root.

**For development** (two terminals; Node.js 22+ and Python 3.12+):

```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/uvicorn app.main:app --reload            # http://localhost:8000
```

```bash
cd frontend
npm install
npm run dev                                         # http://localhost:5173
```

The front end forwards API calls to the backend. To switch on live answers from Claude, add
`AI_PROVIDER=anthropic` and `ANTHROPIC_API_KEY=<your key>` to `backend/.env` (never commit it).
Every setting is listed in [backend/.env.example](backend/.env.example) and
[backend/README.md](backend/README.md).

**Tests** (the same commands CI runs):

```bash
cd backend && .venv/bin/pytest          # calculator, figure checks, API, accounts, data deletion
cd frontend && npm test                  # calculator, conversation branching, full user flows
```

## How it works

### The conversation

One question at a time ([`FLOW` in profile.ts](frontend/src/domain/profile.ts)); each answer is
saved to its own field. The six inputs the brief names:

| Brief input | Fields | Read by the calculation |
|---|---|---|
| People who depend on their income | `deps`, `children`, `youngest` | years of support, college |
| Income to replace | `income`, `years` | income replacement |
| Mortgage and other debts | `mortgage`, `mortgageYears`, `otherDebt` | debts to clear, matching term |
| Education and future expenses | `college` | college |
| Cover already held | `group`, `policies`, `savings` | coverage in place |
| What they can afford | `monthlyBudget` (plus the `budget` preference) | budget figures and trade-off; term vs. permanent |

Questions are skipped or reworded by earlier answers: no children means no questions about
children's ages or college; no one depending on them means no years-of-support question; no
mortgage means no mortgage-term question. Two families get different sequences, for example
(tested in [profile.test.ts](frontend/src/domain/profile.test.ts)):

- *Partner and two kids, mortgage:* who depends on you → how many children → youngest's age →
  income → years of support → mortgage → years left on it → other debts → college → work
  coverage → own policies → savings → monthly budget → five coverage-type questions.
- *No dependants, renting:* who depends on you → income → mortgage → other debts → work coverage
  → own policies → savings → monthly budget → five coverage-type questions.

### The cover amount and its arithmetic

`compute()` in [needs.ts](frontend/src/domain/needs.ts) (mirrored on the server in
[compass.py](backend/app/domain/compass.py)) turns the answers into the amount: 75% of income ×
years of support, plus debts, college and final expenses, minus coverage in place, rounded up to
$25,000, with a ±15% range. The Breakdown tab shows every line with its inputs, what moves the
amount most (each part's share, and the computed effect of one more year or $10,000 more income),
and why it's a range. Changing any answer in My info recalculates at once and says how far the
starting point moved.

### The AI explains; the code computes

Claude reads free-text answers into fields (validated like any input) and answers questions in
Chat. Every dollar figure in its answer is checked against the computed amounts before it is shown
([figures.py](backend/app/domain/figures.py)); any other figure means a standard answer is shown
instead, and the app says why. If the model is unavailable, slow or fails, onboarding and Chat
carry on with the built-in parser and standard answers, and nothing entered is lost.

### Personal data

What is kept, where and for how long is in [docs/data-handling.md](docs/data-handling.md).

## Repository layout

| Folder | Contents |
|---|---|
| [backend/](backend/) | FastAPI service: calculator, accounts, AI adapter, tests. See [backend/README.md](backend/README.md). |
| [frontend/](frontend/) | React + TypeScript client (Vite). See [frontend/README.md](frontend/README.md). |
| [docs/](docs/) | [Data handling](docs/data-handling.md); the front-end handoff spec, prototype and design tokens. |
| [Dockerfile](Dockerfile) | The whole app in one container. (AWS uses [backend/Dockerfile](backend/Dockerfile) and Amplify.) |
| [.github/workflows/](.github/workflows/) | CI, and deploying the backend to AWS. |
| [amplify.yml](amplify.yml), [customHttp.yml](customHttp.yml) | AWS Amplify build and security headers for the front end. |
