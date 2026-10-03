# syntax=docker/dockerfile:1
# Before deploying, pin both base images by digest:
#   docker buildx imagetools inspect python:3.12-slim
# and replace the tag with python:3.12-slim@sha256:<digest>.

FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
WORKDIR /build
COPY pyproject.toml ./
COPY app ./app
RUN pip install .

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH
RUN useradd --system --uid 10001 --no-create-home appuser
COPY --from=builder /opt/venv /opt/venv
WORKDIR /srv
USER 10001
EXPOSE 8000
# One worker: the in-memory repository is per-process. Scale out only after the
# Postgres repository replaces it. uvicorn's access log is off because it prints raw
# paths (which contain session IDs); the app logs a redacted line per request instead.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-access-log"]
