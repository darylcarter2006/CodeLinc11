"""Async SQLAlchemy engine and per-call session factory.

The engine is created once at startup (see ``app.container.build_repository``) and
disposed on shutdown (see the lifespan in ``app.main``).
"""

from __future__ import annotations

import ssl
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def connect_args(ssl_root_cert: str | None) -> dict[str, Any]:
    """asyncpg connection options.

    With a CA bundle (for RDS: global-bundle.pem), the server certificate and hostname
    are verified, which is the equivalent of ``sslmode=verify-full``. Without one, asyncpg
    uses its default (encrypt if the server supports it, without verification), so local
    Docker Postgres works unchanged.
    """
    if ssl_root_cert is None:
        return {}
    context = ssl.create_default_context(cafile=ssl_root_cert)
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    return {"ssl": context}


def build_engine(
    database_url: str,
    *,
    pool_size: int = 10,
    max_overflow: int = 5,
    ssl_root_cert: str | None = None,
) -> None:
    """Initialise the module-level engine. Call once at application startup."""
    global _engine, _session_factory
    _engine = create_async_engine(
        database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        # Detect connections dropped by the server or network before using them.
        pool_pre_ping=True,
        connect_args=connect_args(ssl_root_cert),
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


@asynccontextmanager
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """One transaction: commits on success, rolls back on any exception."""
    if _session_factory is None:
        raise RuntimeError("Database engine not initialised. Call build_engine() first.")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_engine() -> None:
    """Graceful shutdown: drain the connection pool."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
