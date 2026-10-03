"""PostgreSQL implementation of SessionRepository, backed by SQLAlchemy 2 async.

Optimistic locking: every write that touches a session row uses a WHERE revision =
expected_revision predicate. If the row was updated by another request first, no row
is returned and StaleRevision is raised; nothing in that transaction is written.

Concurrency limitation: ``session_lock`` is the base-class no-op here. Two concurrent
requests with the same client_request_id can both call the AI model; the first to
commit wins and the second receives 409 stale_revision (a retry then replays the
stored response). A pending idempotency record inserted before the model call would
close this gap; ``is_pending`` is reserved for that.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy import update as sa_update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AssessmentRow,
    IdempotencyRow,
    MessageRow,
    SessionRow,
    TokenRow,
)
from app.db.session import close_engine, db_session
from app.domain.assessment import AssessmentBreakdown
from app.domain.profile import Profile
from app.domain.records import (
    AssessmentRecord,
    ConversationState,
    IdempotencyRecord,
    MessageRecord,
    SessionRecord,
    TokenRecord,
)
from app.errors import NotFound, StaleRevision
from app.repositories.base import SessionRepository, SessionUpdate

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------


def _session_from_row(row: SessionRow) -> SessionRecord:
    return SessionRecord(
        id=row.id,
        revision=row.revision,
        turn_count=row.turn_count,
        status=row.status,
        schema_version=row.schema_version,
        profile=Profile.model_validate(row.profile),
        conversation_state=ConversationState.model_validate(row.conversation_state),
        expires_at=row.expires_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _token_from_row(row: TokenRow) -> TokenRecord:
    return TokenRecord(
        token_hash=row.token_hash,
        session_id=row.session_id,
        expires_at=row.expires_at,
        created_at=row.created_at,
    )


def _message_from_row(row: MessageRow) -> MessageRecord:
    return MessageRecord(
        id=row.id,
        session_id=row.session_id,
        role=row.role,
        content=row.content,
        turn_id=row.turn_id,
        created_at=row.created_at,
    )


def _assessment_from_row(row: AssessmentRow) -> AssessmentRecord:
    return AssessmentRecord(
        id=row.id,
        session_id=row.session_id,
        profile_revision=row.profile_revision,
        profile_snapshot=Profile.model_validate(row.profile_snapshot),
        result=AssessmentBreakdown.model_validate(row.result),
        created_at=row.created_at,
    )


def _idempotency_from_row(row: IdempotencyRow) -> IdempotencyRecord:
    return IdempotencyRecord(
        session_id=row.session_id,
        client_request_id=row.client_request_id,
        request_hash=row.request_hash,
        status_code=row.status_code,
        response=row.response_cache,
        created_at=row.created_at,
        expires_at=row.expires_at,
    )


# ---------------------------------------------------------------------------
# Repository
# ---------------------------------------------------------------------------


class PostgresSessionRepository(SessionRepository):
    """All methods open their own db_session; no session is held across calls."""

    def __init__(self, max_messages_per_session: int = 20) -> None:
        self._max_messages = max_messages_per_session

    async def create_session(self, session: SessionRecord, token: TokenRecord) -> None:
        async with db_session() as db:
            db.add(
                SessionRow(
                    id=session.id,
                    revision=session.revision,
                    turn_count=session.turn_count,
                    status=session.status,
                    schema_version=session.schema_version,
                    profile=session.profile.model_dump(mode="json"),
                    conversation_state=session.conversation_state.model_dump(mode="json"),
                    expires_at=session.expires_at,
                    created_at=session.created_at,
                    updated_at=session.updated_at,
                )
            )
            db.add(
                TokenRow(
                    token_hash=token.token_hash,
                    session_id=token.session_id,
                    expires_at=token.expires_at,
                    created_at=token.created_at,
                )
            )

    async def get_session(self, session_id: str) -> SessionRecord | None:
        async with db_session() as db:
            row = await db.get(SessionRow, session_id)
            return _session_from_row(row) if row is not None else None

    async def delete_session(self, session_id: str) -> None:
        async with db_session() as db:
            # Cascade deletes handle child rows (messages, assessments, tokens,
            # idempotency records) via ON DELETE CASCADE.
            await db.execute(delete(SessionRow).where(SessionRow.id == session_id))

    async def commit(self, session_id: str, update: SessionUpdate, now: datetime) -> SessionRecord:
        async with db_session() as db:
            result = await db.execute(
                sa_update(SessionRow)
                .where(
                    SessionRow.id == session_id,
                    SessionRow.revision == update.expected_revision,
                )
                .values(
                    profile=update.profile.model_dump(mode="json"),
                    conversation_state=update.conversation_state.model_dump(mode="json"),
                    revision=SessionRow.revision + 1,
                    turn_count=(
                        SessionRow.turn_count + 1
                        if update.increment_turn
                        else SessionRow.turn_count
                    ),
                    updated_at=now,
                )
                .returning(
                    SessionRow.id,
                    SessionRow.revision,
                    SessionRow.turn_count,
                    SessionRow.status,
                    SessionRow.schema_version,
                    SessionRow.profile,
                    SessionRow.conversation_state,
                    SessionRow.expires_at,
                    SessionRow.created_at,
                    SessionRow.updated_at,
                )
            )
            row = result.one_or_none()
            if row is None:
                # Either the session doesn't exist or the revision didn't match.
                current_rev = await db.scalar(
                    select(SessionRow.revision).where(SessionRow.id == session_id)
                )
                if current_rev is None:
                    raise NotFound()
                raise StaleRevision(current_revision=current_rev)

            if update.messages:
                db.add_all(
                    MessageRow(
                        id=m.id,
                        session_id=m.session_id,
                        role=m.role,
                        content=m.content,
                        turn_id=m.turn_id,
                        created_at=m.created_at,
                    )
                    for m in update.messages
                )
                await db.flush()
                await _prune_messages(db, session_id, keep=self._max_messages)

            if update.idempotency is not None:
                idem = update.idempotency
                # Upsert keyed by (session_id, client_request_id); a conflict can only
                # come from this same session.
                await db.execute(
                    pg_insert(IdempotencyRow)
                    .values(
                        client_request_id=idem.client_request_id,
                        session_id=idem.session_id,
                        request_hash=idem.request_hash,
                        status_code=idem.status_code,
                        response_cache=idem.response,
                        is_pending=False,
                        created_at=idem.created_at,
                        expires_at=idem.expires_at,
                    )
                    .on_conflict_do_update(
                        index_elements=["session_id", "client_request_id"],
                        set_={
                            "request_hash": idem.request_hash,
                            "status_code": idem.status_code,
                            "response_cache": idem.response,
                            "is_pending": False,
                            "expires_at": idem.expires_at,
                        },
                    )
                )

            # Build a SessionRecord from the RETURNING columns.
            return SessionRecord(
                id=row.id,
                revision=row.revision,
                turn_count=row.turn_count,
                status=row.status,
                schema_version=row.schema_version,
                profile=Profile.model_validate(row.profile),
                conversation_state=ConversationState.model_validate(row.conversation_state),
                expires_at=row.expires_at,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )

    async def get_token(self, token_hash: str) -> TokenRecord | None:
        async with db_session() as db:
            row = await db.get(TokenRow, token_hash)
            return _token_from_row(row) if row is not None else None

    async def replace_tokens(
        self, session_id: str, token: TokenRecord, session_expires_at: datetime
    ) -> None:
        async with db_session() as db:
            await db.execute(delete(TokenRow).where(TokenRow.session_id == session_id))
            db.add(
                TokenRow(
                    token_hash=token.token_hash,
                    session_id=token.session_id,
                    expires_at=token.expires_at,
                    created_at=token.created_at,
                )
            )
            await db.execute(
                sa_update(SessionRow)
                .where(SessionRow.id == session_id)
                .values(expires_at=session_expires_at)
            )

    async def get_idempotency(
        self, session_id: str, client_request_id: str
    ) -> IdempotencyRecord | None:
        async with db_session() as db:
            row = await db.get(IdempotencyRow, (session_id, client_request_id))
            return _idempotency_from_row(row) if row is not None else None

    async def list_messages(self, session_id: str, limit: int) -> list[MessageRecord]:
        if limit <= 0:
            return []
        async with db_session() as db:
            result = await db.execute(
                select(MessageRow)
                .where(MessageRow.session_id == session_id)
                .order_by(MessageRow.seq.desc())
                .limit(limit)
            )
            rows = list(reversed(result.scalars().all()))
            return [_message_from_row(r) for r in rows]

    async def add_assessment(self, assessment: AssessmentRecord) -> None:
        async with db_session() as db:
            db.add(
                AssessmentRow(
                    id=assessment.id,
                    session_id=assessment.session_id,
                    profile_revision=assessment.profile_revision,
                    profile_snapshot=assessment.profile_snapshot.model_dump(mode="json"),
                    result=assessment.result.model_dump(mode="json"),
                    created_at=assessment.created_at,
                )
            )

    async def get_latest_assessment(self, session_id: str) -> AssessmentRecord | None:
        async with db_session() as db:
            result = await db.execute(
                select(AssessmentRow)
                .where(AssessmentRow.session_id == session_id)
                .order_by(AssessmentRow.created_at.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
            return _assessment_from_row(row) if row is not None else None

    async def purge_expired(self, now: datetime) -> int:
        async with db_session() as db:
            # Cascade handles child rows.
            result = await db.execute(
                delete(SessionRow).where(SessionRow.expires_at < now).returning(SessionRow.id)
            )
            count = len(result.all())
            # Purge orphaned idempotency records whose sessions were already deleted
            # or whose own TTL elapsed.
            await db.execute(delete(IdempotencyRow).where(IdempotencyRow.expires_at < now))
            return count

    async def aclose(self) -> None:
        await close_engine()

    async def ping(self) -> bool:
        try:
            async with db_session() as db:
                await db.execute(select(func.now()))
            return True
        except Exception:
            logger.warning("postgres_ping_failed")
            return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _prune_messages(db: AsyncSession, session_id: str, keep: int) -> None:
    """Delete all but the ``keep`` most recent messages for a session."""
    subq = (
        select(MessageRow.id)
        .where(MessageRow.session_id == session_id)
        .order_by(MessageRow.seq.desc())
        .limit(keep)
        .subquery()
    )
    await db.execute(
        delete(MessageRow).where(
            MessageRow.session_id == session_id,
            MessageRow.id.not_in(select(subq.c.id)),
        )
    )
