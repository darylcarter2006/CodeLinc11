"""Application factory. Run locally with: uvicorn app.main:app --reload"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    account,
    ai,
    assessments,
    auth,
    content,
    health,
    messages,
    profiles,
    sessions,
    support,
)
from app.container import Container, build_container
from app.errors import NotFound
from app.logging_config import configure_logging
from app.middleware.error_handlers import register_error_handlers
from app.middleware.request_context import REQUEST_ID_HEADER, RequestContextMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.settings import Settings, get_settings

logger = logging.getLogger(__name__)


async def _sweep_forever(container: Container) -> None:
    """Delete expired personal data now, then every RETENTION_SWEEP_HOURS.

    See docs/data-handling.md.
    """
    while True:
        try:
            await container.personal_data.sweep()
        except Exception:
            logger.warning("retention_sweep_failed")
        await asyncio.sleep(container.settings.retention_sweep_hours * 3600)


def _lifespan(container: Container) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        # Tests call the sweep directly instead.
        sweeper = (
            asyncio.create_task(_sweep_forever(container))
            if container.settings.env != "test"
            else None
        )
        yield
        if sweeper is not None:
            sweeper.cancel()
        await container.repo.aclose()

    return lifespan


def _serve_front_end(app: FastAPI, root: Path) -> None:
    """Serve the built single-page app: real files as they are, any other page as index.html
    (the app's router handles it). API paths are never answered with the page."""
    index = root / "index.html"
    if not index.is_file():
        raise RuntimeError(f"STATIC_DIR has no index.html: {root}")
    app.mount("/assets", StaticFiles(directory=root / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def page(path: str) -> FileResponse:
        if path.startswith(("v1/", "v1")):
            raise NotFound()
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root.resolve()):
            return FileResponse(candidate)
        return FileResponse(index)


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()
    container = container or build_container(settings)
    if settings.env != "test":
        configure_logging(settings.log_level)

    show_docs = settings.env in ("local", "test", "dev")
    app = FastAPI(
        title="Life-insurance needs analyzer API",
        version="0.1.0",
        description="Planning estimates only: not a quote, underwriting decision, "
        "or product recommendation.",
        # Interactive docs only on a developer's machine, never on a deployed service.
        docs_url="/docs" if show_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if show_docs else None,
        lifespan=_lifespan(container),
    )
    app.state.container = container

    register_error_handlers(app)

    v1 = APIRouter(prefix="/v1")
    for module in (health, auth, account, ai, support):
        v1.include_router(module.router)
    if settings.planner_api_enabled:
        # The original Planner session API; the current front end doesn't call it.
        for module in (sessions, profiles, messages, assessments, content):
            v1.include_router(module.router)
    app.include_router(v1)

    if settings.static_dir:
        _serve_front_end(app, Path(settings.static_dir))

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        # Auth is a bearer header, not cookies, so credentials are not needed.
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    # Added last so it runs outermost: every response, including CORS rejections,
    # 413s and 500s, gets an X-Request-ID.
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.env in ("demo", "prod"))
    app.add_middleware(RequestContextMiddleware, max_body_bytes=settings.max_body_bytes)
    return app


app = create_app()
