"""Alembic environment: runs migrations against the async SQLAlchemy engine."""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.models import Base
from app.db.session import connect_args

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Read the connection from the environment so alembic.ini never stores credentials.
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    raise SystemExit("Set DATABASE_URL (postgresql+asyncpg://...) before running alembic.")
DB_SSL_ROOT_CERT = os.environ.get("DB_SSL_ROOT_CERT") or None


def run_migrations_offline() -> None:
    """Emit migration SQL to stdout without a live connection (useful for review)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


async def _run_async() -> None:
    engine = create_async_engine(DATABASE_URL, connect_args=connect_args(DB_SSL_ROOT_CERT))
    async with engine.connect() as conn:
        await conn.run_sync(
            lambda sync_conn: context.configure(
                connection=sync_conn,
                target_metadata=target_metadata,
                compare_type=True,
            )
        )
        async with conn.begin():
            await conn.run_sync(lambda _: context.run_migrations())
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(_run_async())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
