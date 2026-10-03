"""Application factory. Run locally with: uvicorn app.main:app --reload"""

from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import assessments, content, health, messages, profiles, sessions
from app.container import Container, build_container
from app.logging_config import configure_logging
from app.middleware.error_handlers import register_error_handlers
from app.middleware.request_context import REQUEST_ID_HEADER, RequestContextMiddleware
from app.settings import Settings, get_settings


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()
    container = container or build_container(settings)
    if settings.env != "test":
        configure_logging(settings.log_level)

    app = FastAPI(
        title="Life-insurance needs analyzer API",
        version="0.1.0",
        description="Planning estimates only: not a quote, underwriting decision, "
        "or product recommendation.",
        # Interactive docs only outside production.
        docs_url=None if settings.env == "prod" else "/docs",
        redoc_url=None,
        openapi_url=None if settings.env == "prod" else "/openapi.json",
    )
    app.state.container = container

    register_error_handlers(app)

    v1 = APIRouter(prefix="/v1")
    for module in (health, sessions, profiles, messages, assessments, content):
        v1.include_router(module.router)
    app.include_router(v1)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        # Auth is a bearer header, not cookies, so credentials are not needed.
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    # Added last so it runs outermost: every response, including CORS rejections,
    # 413s and 500s, gets an X-Request-ID.
    app.add_middleware(RequestContextMiddleware, max_body_bytes=settings.max_body_bytes)
    return app


app = create_app()
