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
# Amazon RDS CA bundle, so the API can verify the database's certificate (DB_SSL_ROOT_CERT).
# Fetched at build time: certs/ is gitignored, and slim images have no curl.
RUN python -c "import urllib.request as u; u.urlretrieve('https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem', '/build/rds-global-bundle.pem')" \
    && grep -q "BEGIN CERTIFICATE" /build/rds-global-bundle.pem

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH
RUN useradd --system --uid 10001 --no-create-home appuser
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /build/rds-global-bundle.pem /srv/certs/rds-global-bundle.pem
WORKDIR /srv
USER 10001
EXPOSE 8000
# Behind a load balancer, set FORWARDED_ALLOW_IPS to the load balancer's network (for ECS in
# the default VPC: 172.31.0.0/16) so rate limits see each client's real IP. Never use "*":
# that lets clients forge their address. uvicorn's access log is off because it prints raw
# paths (which contain session IDs); the app logs a redacted line per request instead.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-access-log"]
