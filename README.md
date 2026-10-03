# CodeLinc11

Life-insurance needs analyzer: a guided planning tool that estimates a household's coverage gap.

## Repository layout

| Folder | Contents |
|---|---|
| [backend/](backend/) | FastAPI service, calculator, tests. See [backend/README.md](backend/README.md). |
| [backend/docs/](backend/docs/) | Backend blueprint (design document). |
| [frontend/](frontend/) | Coverage Compass: React + TypeScript client (Vite). See [frontend/README.md](frontend/README.md). |
| [docs/coverage-compass/](docs/coverage-compass/) | Front-end handoff spec, prototype and design tokens. |
| [.github/workflows/](.github/workflows/) | CI, one workflow per app. |
| [amplify.yml](amplify.yml) | AWS Amplify Hosting build for the front end. Setup steps: [frontend/README.md](frontend/README.md#deploying-to-aws-amplify). |
