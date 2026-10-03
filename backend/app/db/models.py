"""SQLAlchemy ORM table definitions.

These map directly to the DDL in docs/blueprint.md §7.
Domain records (app.domain.records) are the source of truth for field names;
the ORM columns here must stay in sync.
"""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import DeclarativeBase, MappedColumn, mapped_column


class Base(DeclarativeBase):
    pass


class SessionRow(Base):
    __tablename__ = "sessions"

    id: MappedColumn[str] = mapped_column(Text, primary_key=True)
    revision: MappedColumn[int] = mapped_column(Integer, nullable=False, default=0)
    turn_count: MappedColumn[int] = mapped_column(Integer, nullable=False, default=0)
    status: MappedColumn[str] = mapped_column(Text, nullable=False, default="active")
    schema_version: MappedColumn[str] = mapped_column(Text, nullable=False, default="v1")
    # profile and conversation_state are JSONB so they evolve without new migrations.
    profile: MappedColumn[dict[str, object]] = mapped_column(JSONB, nullable=False, default={})
    conversation_state: MappedColumn[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default={}
    )
    expires_at: MappedColumn[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    created_at: MappedColumn[object] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: MappedColumn[object] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class MessageRow(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_session_seq", "session_id", "seq"),)

    id: MappedColumn[str] = mapped_column(Text, primary_key=True)
    # Insertion order. A turn's user and assistant messages share created_at, so
    # ordering must use this column, never the timestamp.
    seq: MappedColumn[int] = mapped_column(BigInteger, Identity(always=True), nullable=False)
    session_id: MappedColumn[str] = mapped_column(
        Text, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: MappedColumn[str] = mapped_column(Text, nullable=False)
    content: MappedColumn[str] = mapped_column(Text, nullable=False)
    turn_id: MappedColumn[str] = mapped_column(Text, nullable=False)
    created_at: MappedColumn[object] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class AssessmentRow(Base):
    __tablename__ = "assessments"
    __table_args__ = (Index("ix_assessments_session_created", "session_id", "created_at"),)

    id: MappedColumn[str] = mapped_column(Text, primary_key=True)
    session_id: MappedColumn[str] = mapped_column(
        Text, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    profile_revision: MappedColumn[int] = mapped_column(Integer, nullable=False)
    profile_snapshot: MappedColumn[dict[str, object]] = mapped_column(JSONB, nullable=False)
    result: MappedColumn[dict[str, object]] = mapped_column(JSONB, nullable=False)
    created_at: MappedColumn[object] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class TokenRow(Base):
    __tablename__ = "session_tokens"
    __table_args__ = (Index("ix_tokens_session", "session_id"),)

    token_hash: MappedColumn[str] = mapped_column(Text, primary_key=True)
    session_id: MappedColumn[str] = mapped_column(
        Text, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: MappedColumn[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    created_at: MappedColumn[object] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class IdempotencyRow(Base):
    __tablename__ = "idempotency_records"

    # Keyed per session: the same client_request_id in two sessions is two records.
    session_id: MappedColumn[str] = mapped_column(
        Text, ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    client_request_id: MappedColumn[str] = mapped_column(Text, primary_key=True)
    request_hash: MappedColumn[str] = mapped_column(Text, nullable=False)
    status_code: MappedColumn[int] = mapped_column(Integer, nullable=False)
    response_cache: MappedColumn[dict[str, object]] = mapped_column(JSONB, nullable=False)
    # Reserved for a future "in-flight" placeholder; always False today.
    is_pending: MappedColumn[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: MappedColumn[object] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: MappedColumn[object] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
