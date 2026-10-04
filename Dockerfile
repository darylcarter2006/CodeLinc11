# syntax=docker/dockerfile:1
# Coverage Compass in one container: the React front end, served by the FastAPI backend.
#
#   docker build -t coverage-compass .
#   docker run --rm -p 8000:8000 coverage-compass      # then open http://localhost:8000
#
# Runs with no network, credentials or database: accounts and saved answers are kept in memory,
# onboarding uses the built-in answer parser, Chat gives standard answers, and password reset
# emails are printed to the container's log. (The AWS deployment uses backend/Dockerfile.)

FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# Same origin as the API, and no Google client ID: the Google button explains it isn't set up.
ENV VITE_API_BASE_URL= VITE_GOOGLE_CLIENT_ID=
RUN npm run build

FROM python:3.12-slim AS api
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
WORKDIR /build
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN pip install .

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH \
    ENV=local \
    REPOSITORY_BACKEND=memory \
    AI_PROVIDER=stub \
    EMAIL_PROVIDER=outbox \
    APP_BASE_URL=http://localhost:8000 \
    CORS_ORIGINS=http://localhost:8000 \
    STATIC_DIR=/srv/web
RUN useradd --system --uid 10001 --no-create-home appuser
COPY --from=api /opt/venv /opt/venv
COPY --from=web /web/dist /srv/web
WORKDIR /srv
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD ["python", "-c", "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/v1/health', timeout=2)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
