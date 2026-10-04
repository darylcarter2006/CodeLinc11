# CodeLinc11

Life-insurance needs analyzer: a guided planning tool that estimates a household's coverage gap.

## How to run

**Just the app (no backend needed).** Requires [Node.js](https://nodejs.org) 22+ and Git.

```bash
git clone https://github.com/darylcarter2006/CodeLinc11.git
cd CodeLinc11/frontend
npm install
npm run dev
```

Open **http://localhost:5173**. To look around without signing up, click **"Explore with example
data instead"**. Without a backend, accounts are saved in your browser, onboarding uses the
built-in answer parser, and Chat gives standard answers.

**With the backend** (server-checked Google sign-in, and live answers from Claude once an API key is set).
Requires Python 3.12+. In a second terminal:

```bash
cd CodeLinc11/backend
python3 -m venv .venv                        # Windows: python -m venv .venv
.venv/bin/pip install -e ".[dev]"            # Windows: .venv\Scripts\pip install -e ".[dev]"
.venv/bin/uvicorn app.main:app --reload      # Windows: .venv\Scripts\uvicorn app.main:app --reload
```

The front end forwards API calls to `http://localhost:8000` automatically. Until Claude is switched
on, the backend reports AI as unavailable and the app keeps using the built-in parser and standard
answers. To switch it on, add `AI_PROVIDER=anthropic` and `ANTHROPIC_API_KEY=<your key>` to
`backend/.env` (never commit it) and restart the backend. Settings such as the AI provider and Google client ID are in
[backend/README.md](backend/README.md) and [frontend/README.md](frontend/README.md).

## Repository layout

| Folder | Contents |
|---|---|
| [backend/](backend/) | FastAPI service, calculator, tests. See [backend/README.md](backend/README.md). |
| [backend/docs/](backend/docs/) | Backend blueprint (design document). |
| [frontend/](frontend/) | Coverage Compass: React + TypeScript client (Vite). See [frontend/README.md](frontend/README.md). |
| [docs/coverage-compass/](docs/coverage-compass/) | Front-end handoff spec, prototype and design tokens. |
| [.github/workflows/](.github/workflows/) | CI, one workflow per app. |
| [amplify.yml](amplify.yml) | AWS Amplify Hosting build for the front end. Setup steps: [frontend/README.md](frontend/README.md#deploying-to-aws-amplify). |
